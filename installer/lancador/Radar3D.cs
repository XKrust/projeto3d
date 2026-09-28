// Radar3D.exe — lançador do Radar 3D instalado (ver docs/instalador.md).
//
// Sem nenhuma janela de console: backend (Python) e telas (Node) rodam escondidos, com a
// saída gravada em %LOCALAPPDATA%\Radar3D\data\*.log. Mostra uma janelinha de progresso
// ao abrir e fica como ícone perto do relógio (Abrir / Pasta dos dados / Sair). Se uma
// parte cair, reinicia sozinha. Ao sair, fecha tudo junto.
//
// Compilado no GitHub Actions com o csc do .NET Framework 4.x (installer/montar.ps1), que
// só aceita C# 5: nada de $"...", ?. ou nameof.
//
// Uso: Radar3D.exe            abre (ou só abre o navegador, se já estiver aberto)
//      Radar3D.exe --sair     fecha o Radar 3D que estiver aberto
// RADAR_NO_BROWSER=1 não abre o navegador (teste automático).

using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace Radar3D
{
    static class Program
    {
        public const string MutexName = "Local\\Radar3D-Lancador";
        public const string ExitEventName = "Local\\Radar3D-Sair";

        [STAThread]
        static int Main(string[] args)
        {
            bool sair = Array.IndexOf(args, "--sair") >= 0;
            try { SetProcessDPIAware(); } catch (Exception) { }

            bool created;
            Mutex mutex = new Mutex(true, MutexName, out created);
            if (!created)
            {
                if (sair)
                {
                    SignalExit();
                    Launcher.WaitPortsFree(20000);
                    return 0;
                }
                Launcher.OpenBrowser();
                return 0;
            }
            if (sair)
            {
                // Nenhum lançador aberto: fecha o que tiver sobrado nas portas do Radar 3D.
                Launcher.KillPorts();
                mutex.ReleaseMutex();
                return 0;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Launcher launcher = new Launcher();
            Application.Run(launcher);
            GC.KeepAlive(mutex);
            return launcher.ExitCode;
        }

        static void SignalExit()
        {
            try
            {
                EventWaitHandle ev;
                if (EventWaitHandle.TryOpenExisting(ExitEventName, out ev)) ev.Set();
            }
            catch (Exception) { }
        }

        [DllImport("user32.dll")]
        static extern bool SetProcessDPIAware();
    }

    sealed class Launcher : ApplicationContext
    {
        const int BackendPort = 8000;
        const int FrontendPort = 3000;
        const string Url = "http://localhost:3000/";

        readonly string app;       // pasta do programa (onde está este .exe)
        readonly string baseDir;   // %LOCALAPPDATA%\Radar3D
        readonly string dataDir;   // %LOCALAPPDATA%\Radar3D\data
        readonly NotifyIcon tray;
        readonly SplashForm splash;
        readonly IntPtr job;
        readonly object logLock = new object();

        Process backend;
        Process frontend;
        volatile bool quitting;
        volatile bool ready;
        int backendRestarts;
        int frontendRestarts;
        public int ExitCode;

        public Launcher()
        {
            app = AppDomain.CurrentDomain.BaseDirectory;
            baseDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Radar3D");
            dataDir = Path.Combine(baseDir, "data");
            Directory.CreateDirectory(dataDir);
            job = JobObject.Create();

            Icon icon = LoadIcon();
            splash = new SplashForm(icon);
            tray = new NotifyIcon();
            tray.Icon = icon;
            tray.Text = "Radar 3D — abrindo…";
            tray.ContextMenuStrip = BuildMenu();
            tray.DoubleClick += delegate { OpenBrowser(); };
            tray.Visible = true;
            splash.Show();

            Thread exitWatcher = new Thread(WatchExitEvent);
            exitWatcher.IsBackground = true;
            exitWatcher.Start();

            Thread boot = new Thread(Boot);
            boot.IsBackground = true;
            boot.Start();
        }

        Icon LoadIcon()
        {
            try { return Icon.ExtractAssociatedIcon(Application.ExecutablePath); }
            catch (Exception) { return SystemIcons.Application; }
        }

        ContextMenuStrip BuildMenu()
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem abrir = new ToolStripMenuItem("Abrir o Radar 3D");
            abrir.Font = new Font(abrir.Font, FontStyle.Bold);
            abrir.Click += delegate { OpenBrowser(); };
            ToolStripMenuItem pasta = new ToolStripMenuItem("Pasta dos dados e registros");
            pasta.Click += delegate { Process.Start("explorer.exe", "\"" + dataDir + "\""); };
            ToolStripMenuItem sair = new ToolStripMenuItem("Sair do Radar 3D");
            sair.Click += delegate { Quit(); };
            menu.Items.Add(abrir);
            menu.Items.Add(pasta);
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(sair);
            return menu;
        }

        // ---------------------------------------------------------------- inicialização

        void Boot()
        {
            try
            {
                if (Healthy(FrontendPort))
                {
                    // Sobrou um Radar 3D rodando (lançador fechado à força): reaproveita.
                    SetReady();
                    return;
                }
                if (PortBusy(FrontendPort) || PortBusy(BackendPort))
                {
                    KillPorts();
                    Thread.Sleep(1500);
                    if (PortBusy(FrontendPort) || PortBusy(BackendPort))
                    {
                        Fail("Outro programa está usando a porta 3000 ou 8000, que o Radar 3D precisa.\n\n" +
                             "Feche esse programa (ou reinicie o computador) e abra o Radar 3D de novo.", null);
                        return;
                    }
                }

                if (!PrepareBackend()) return;

                Status("Iniciando o Radar 3D…");
                backend = StartBackend();
                if (!WaitHealthy(BackendPort, 180, backend))
                {
                    Fail("O Radar 3D não conseguiu iniciar (parte do servidor).", "backend.log");
                    return;
                }
                Status("Abrindo as telas…");
                frontend = StartFrontend();
                if (!WaitHealthy(FrontendPort, 90, frontend))
                {
                    Fail("O Radar 3D não conseguiu iniciar (parte das telas).", "frontend.log");
                    return;
                }
                SetReady();
            }
            catch (Exception ex)
            {
                Fail("Erro ao abrir o Radar 3D: " + ex.Message, "lancador.log");
                Log("lancador.log", ex.ToString());
            }
        }

        bool PrepareBackend()
        {
            string versao = File.ReadAllText(Path.Combine(app, "VERSION")).Trim();
            string venv = Path.Combine(baseDir, "venv");
            string marker = Path.Combine(venv, "radar3d-versao.txt");
            string python = Path.Combine(venv, "Scripts\\python.exe");
            string preparada = File.Exists(marker) ? File.ReadAllText(marker).Trim() : "";
            if (preparada == versao && File.Exists(python)) return true;

            Status("Preparando o Radar 3D pela primeira vez: baixando o Python e as bibliotecas " +
                   "(uns 100 MB). Pode levar alguns minutos, deixe esta janela aberta.");
            string args = "sync --frozen --no-dev --no-install-project --project \"" + Path.Combine(app, "backend") + "\"";
            Process uv = StartHidden(Path.Combine(app, "runtime\\uv.exe"), args, app, "preparo.log", true);
            uv.WaitForExit();
            if (uv.ExitCode != 0)
            {
                Fail("Não consegui preparar o Radar 3D. Confira a internet e abra de novo.", "preparo.log");
                return false;
            }
            File.WriteAllText(marker, versao);
            return true;
        }

        Process StartBackend()
        {
            string python = Path.Combine(baseDir, "venv\\Scripts\\python.exe");
            string args = "-m uvicorn app.main:app --host 127.0.0.1 --port " + BackendPort;
            Process p = StartHidden(python, args, Path.Combine(app, "backend"), "backend.log", false);
            p.EnableRaisingEvents = true;
            p.Exited += delegate { OnChildExited(true); };
            return p;
        }

        Process StartFrontend()
        {
            string node = Path.Combine(app, "runtime\\node.exe");
            Process p = StartHidden(node, "server.js", Path.Combine(app, "frontend"), "frontend.log", false);
            p.EnableRaisingEvents = true;
            p.Exited += delegate { OnChildExited(false); };
            return p;
        }

        Process StartHidden(string exe, string args, string workDir, string logName, bool showProgress)
        {
            ProcessStartInfo info = new ProcessStartInfo(exe, args);
            info.WorkingDirectory = workDir;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            info.StandardOutputEncoding = Encoding.UTF8;
            info.StandardErrorEncoding = Encoding.UTF8;
            info.EnvironmentVariables["RADAR_DATA_DIR"] = dataDir;
            info.EnvironmentVariables["UV_PYTHON_INSTALL_DIR"] = Path.Combine(baseDir, "python");
            info.EnvironmentVariables["UV_PROJECT_ENVIRONMENT"] = Path.Combine(baseDir, "venv");
            info.EnvironmentVariables["UV_CACHE_DIR"] = Path.Combine(baseDir, "uv-cache");
            info.EnvironmentVariables["UV_PYTHON_PREFERENCE"] = "only-managed";
            info.EnvironmentVariables["UV_NO_PROGRESS"] = "1";
            info.EnvironmentVariables["PYTHONUTF8"] = "1";
            info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            info.EnvironmentVariables["PORT"] = FrontendPort.ToString();
            info.EnvironmentVariables["HOSTNAME"] = "127.0.0.1";
            info.EnvironmentVariables["NODE_ENV"] = "production";

            string logPath = Path.Combine(dataDir, logName);
            RotateLog(logPath);
            Process p = new Process();
            p.StartInfo = info;
            DataReceivedEventHandler handler = delegate(object sender, DataReceivedEventArgs e)
            {
                if (e.Data == null) return;
                Log(logName, e.Data);
                if (showProgress && e.Data.Trim().Length > 0) Detail(e.Data.Trim());
            };
            p.OutputDataReceived += handler;
            p.ErrorDataReceived += handler;
            p.Start();
            JobObject.Assign(job, p);
            p.BeginOutputReadLine();
            p.BeginErrorReadLine();
            return p;
        }

        void SetReady()
        {
            ready = true;
            RunOnUi(delegate
            {
                splash.Hide();
                tray.Text = "Radar 3D — aberto";
                tray.ShowBalloonTip(8000, "Radar 3D aberto",
                    "Ele fica aqui perto do relógio. Para fechar: botão direito no ícone → Sair.", ToolTipIcon.Info);
            });
            if (Environment.GetEnvironmentVariable("RADAR_NO_BROWSER") != "1") OpenBrowser();
        }

        // ---------------------------------------------------------------- se uma parte cair

        void OnChildExited(bool isBackend)
        {
            if (quitting || !ready) return;
            int restarts = isBackend ? ++backendRestarts : ++frontendRestarts;
            Log("lancador.log", string.Format("{0} parou; reiniciando ({1}ª vez)", isBackend ? "backend" : "telas", restarts));
            if (restarts > 3)
            {
                RunOnUi(delegate
                {
                    tray.ShowBalloonTip(10000, "Radar 3D", "Uma parte do Radar 3D parou várias vezes. Feche e abra de novo; " +
                        "se continuar, envie os arquivos da pasta dos dados.", ToolTipIcon.Warning);
                });
                return;
            }
            Thread.Sleep(2000);
            if (quitting) return;
            if (isBackend) backend = StartBackend(); else frontend = StartFrontend();
        }

        // ---------------------------------------------------------------- sair

        void WatchExitEvent()
        {
            EventWaitHandle ev = new EventWaitHandle(false, EventResetMode.AutoReset, Program.ExitEventName);
            ev.WaitOne();
            RunOnUi(Quit);
        }

        void Quit()
        {
            quitting = true;
            KillTree(frontend);
            KillTree(backend);
            KillPorts();
            tray.Visible = false;
            tray.Dispose();
            splash.Close();
            ExitThread();
        }

        static void KillTree(Process p)
        {
            try
            {
                if (p == null || p.HasExited) return;
                RunQuiet("taskkill.exe", "/PID " + p.Id + " /T /F");
            }
            catch (Exception) { }
        }

        public static void KillPorts()
        {
            foreach (int port in new int[] { BackendPort, FrontendPort })
            {
                foreach (int pid in ListeningPids(port)) RunQuiet("taskkill.exe", "/PID " + pid + " /T /F");
            }
        }

        public static void WaitPortsFree(int timeoutMs)
        {
            DateTime limit = DateTime.Now.AddMilliseconds(timeoutMs);
            while (DateTime.Now < limit && (PortBusy(BackendPort) || PortBusy(FrontendPort))) Thread.Sleep(300);
        }

        static int[] ListeningPids(int port)
        {
            // netstat -ano: "  TCP    127.0.0.1:3000   0.0.0.0:0   LISTENING   1234"
            string output = RunQuiet("netstat.exe", "-ano -p TCP");
            System.Collections.Generic.List<int> pids = new System.Collections.Generic.List<int>();
            foreach (string raw in output.Split('\n'))
            {
                string[] cols = raw.Split(new char[] { ' ', '\t', '\r' }, StringSplitOptions.RemoveEmptyEntries);
                if (cols.Length < 5 || cols[3] != "LISTENING") continue;
                if (!cols[1].EndsWith(":" + port)) continue;
                int pid;
                if (int.TryParse(cols[4], out pid) && pid > 0 && !pids.Contains(pid)) pids.Add(pid);
            }
            return pids.ToArray();
        }

        static string RunQuiet(string exe, string args)
        {
            ProcessStartInfo info = new ProcessStartInfo(exe, args);
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            using (Process p = Process.Start(info))
            {
                string output = p.StandardOutput.ReadToEnd();
                p.WaitForExit(15000);
                return output;
            }
        }

        // ---------------------------------------------------------------- utilidades

        public static void OpenBrowser()
        {
            try
            {
                ProcessStartInfo info = new ProcessStartInfo(Url);
                info.UseShellExecute = true;
                Process.Start(info);
            }
            catch (Exception) { }
        }

        static bool Healthy(int port)
        {
            try
            {
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + port + "/api/health");
                req.Timeout = 3000;
                req.Proxy = null;
                using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
                {
                    return resp.StatusCode == HttpStatusCode.OK;
                }
            }
            catch (Exception) { return false; }
        }

        static bool PortBusy(int port)
        {
            foreach (System.Net.IPEndPoint ep in IPGlobalProperties.GetIPGlobalProperties().GetActiveTcpListeners())
            {
                if (ep.Port == port) return true;
            }
            return false;
        }

        bool WaitHealthy(int port, int seconds, Process p)
        {
            DateTime limit = DateTime.Now.AddSeconds(seconds);
            while (DateTime.Now < limit)
            {
                if (Healthy(port)) return true;
                if (p != null && p.HasExited) return false;
                Thread.Sleep(700);
            }
            return false;
        }

        void Fail(string message, string logName)
        {
            ExitCode = 1;
            Log("lancador.log", "FALHA: " + message.Replace("\n", " "));
            quitting = true;
            KillTree(frontend);
            KillTree(backend);
            if (Environment.GetEnvironmentVariable("RADAR_NO_BROWSER") == "1")
            {
                RunOnUi(delegate { tray.Visible = false; ExitThread(); });
                return;
            }
            RunOnUi(delegate
            {
                splash.Hide();
                string text = message;
                if (logName != null) text += "\n\nQuer ver o registro do erro (para mandar para quem está te ajudando)?";
                DialogResult r = MessageBox.Show(text, "Radar 3D", logName != null ? MessageBoxButtons.YesNo : MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
                if (logName != null && r == DialogResult.Yes)
                {
                    try { Process.Start("notepad.exe", "\"" + Path.Combine(dataDir, logName) + "\""); } catch (Exception) { }
                }
                tray.Visible = false;
                ExitThread();
            });
        }

        void Status(string text) { RunOnUi(delegate { splash.SetStatus(text); }); }

        void Detail(string text) { RunOnUi(delegate { splash.SetDetail(text); }); }

        void RunOnUi(MethodInvoker action)
        {
            try
            {
                if (splash.IsHandleCreated && !splash.IsDisposed) splash.BeginInvoke(action);
            }
            catch (Exception) { }
        }

        void RotateLog(string path)
        {
            try
            {
                if (File.Exists(path))
                {
                    string old = path + ".anterior";
                    if (File.Exists(old)) File.Delete(old);
                    File.Move(path, old);
                }
            }
            catch (Exception) { }
        }

        void Log(string logName, string line)
        {
            lock (logLock)
            {
                try
                {
                    File.AppendAllText(Path.Combine(dataDir, logName), line + Environment.NewLine, Encoding.UTF8);
                }
                catch (Exception) { }
            }
        }
    }

    sealed class SplashForm : Form
    {
        readonly Label status;
        readonly Label detail;

        public SplashForm(Icon icon)
        {
            Text = "Radar 3D";
            Icon = icon;
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(460, 170);
            BackColor = Color.FromArgb(20, 17, 16);
            ForeColor = Color.FromArgb(240, 236, 230);
            Font = new Font("Segoe UI", 10f);
            ShowInTaskbar = true;

            PictureBox logo = new PictureBox();
            logo.Image = new Icon(icon, 64, 64).ToBitmap();
            logo.SizeMode = PictureBoxSizeMode.Zoom;
            logo.SetBounds(20, 22, 56, 56);

            Label title = new Label();
            title.Text = "Radar 3D";
            title.Font = new Font("Segoe UI Semibold", 16f);
            title.AutoSize = true;
            title.Location = new Point(92, 20);

            status = new Label();
            status.Text = "Abrindo o Radar 3D…";
            status.SetBounds(92, 56, 350, 44);

            ProgressBar bar = new ProgressBar();
            bar.Style = ProgressBarStyle.Marquee;
            bar.MarqueeAnimationSpeed = 30;
            bar.SetBounds(20, 108, 420, 10);

            detail = new Label();
            detail.ForeColor = Color.FromArgb(150, 145, 138);
            detail.Font = new Font("Segoe UI", 8.5f);
            detail.AutoEllipsis = true;
            detail.SetBounds(20, 128, 420, 30);

            Controls.Add(logo);
            Controls.Add(title);
            Controls.Add(status);
            Controls.Add(bar);
            Controls.Add(detail);
        }

        public void SetStatus(string text) { status.Text = text; }

        public void SetDetail(string text) { detail.Text = text; }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            // Fechar a janelinha não fecha o Radar 3D: ele segue abrindo e fica perto do relógio.
            if (e.CloseReason == CloseReason.UserClosing)
            {
                e.Cancel = true;
                Hide();
                return;
            }
            base.OnFormClosing(e);
        }
    }

    // Processos filhos morrem junto com o lançador, mesmo se ele for fechado à força.
    static class JobObject
    {
        const int JobObjectExtendedLimitInformation = 9;
        const uint KillOnJobClose = 0x2000;

        [StructLayout(LayoutKind.Sequential)]
        struct BasicLimit
        {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public UIntPtr Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct IoCounters
        {
            public ulong ReadOperationCount;
            public ulong WriteOperationCount;
            public ulong OtherOperationCount;
            public ulong ReadTransferCount;
            public ulong WriteTransferCount;
            public ulong OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct ExtendedLimit
        {
            public BasicLimit BasicLimitInformation;
            public IoCounters IoInfo;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryUsed;
            public UIntPtr PeakJobMemoryUsed;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        static extern IntPtr CreateJobObject(IntPtr attributes, string name);

        [DllImport("kernel32.dll")]
        static extern bool SetInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint length);

        [DllImport("kernel32.dll")]
        static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

        public static IntPtr Create()
        {
            try
            {
                IntPtr job = CreateJobObject(IntPtr.Zero, null);
                ExtendedLimit info = new ExtendedLimit();
                info.BasicLimitInformation.LimitFlags = KillOnJobClose;
                int length = Marshal.SizeOf(typeof(ExtendedLimit));
                IntPtr ptr = Marshal.AllocHGlobal(length);
                Marshal.StructureToPtr(info, ptr, false);
                SetInformationJobObject(job, JobObjectExtendedLimitInformation, ptr, (uint)length);
                Marshal.FreeHGlobal(ptr);
                return job;
            }
            catch (Exception) { return IntPtr.Zero; }
        }

        public static void Assign(IntPtr job, Process p)
        {
            if (job == IntPtr.Zero) return;
            try { AssignProcessToJobObject(job, p.Handle); } catch (Exception) { }
        }
    }
}
