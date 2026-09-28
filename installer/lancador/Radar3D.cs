// Radar3D.exe — lançador do Radar 3D instalado (ver docs/instalador.md).
//
// Abre o Radar 3D na própria janela (WebView2, o motor do Edge que já vem no Windows 10/11):
// sem navegador, sem barra de endereço, sem "localhost" à vista. Nenhuma janela de console:
// backend (Python) e telas (Node) rodam escondidos, com a saída em
// %LOCALAPPDATA%\Radar3D\data\*.log. Mostra uma janelinha de progresso ao abrir e fica como
// ícone perto do relógio (Abrir / Pasta dos dados / Sair): fechar a janela não interrompe a
// coleta. Se uma parte cair, reinicia sozinha. Ao sair, fecha tudo junto. Sem o WebView2
// (raro), abre no navegador.
//
// Compilado no GitHub Actions com o csc do .NET Framework 4.x (installer/montar.ps1), que
// só aceita C# 5: nada de $"...", ?. ou nameof.
//
// Uso: Radar3D.exe            abre (ou traz a janela para a frente, se já estiver aberto)
//      Radar3D.exe --sair     fecha o Radar 3D que estiver aberto
// RADAR_NO_BROWSER=1: teste automático (nunca abre o navegador nem caixas de mensagem).

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.NetworkInformation;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

// Sem isto o .NET trata o .exe como feito para o 4.0 e não lê os ícones em PNG do radar3d.ico.
// O WebView2 já exige o 4.6.2 (o Windows 10/11 vem com o 4.8).
[assembly: System.Runtime.Versioning.TargetFramework(".NETFramework,Version=v4.6.2")]

namespace Radar3D
{
    static class Program
    {
        public const string MutexName = "Local\\Radar3D-Lancador";
        public const string ExitEventName = "Local\\Radar3D-Sair";
        public const string ShowEventName = "Local\\Radar3D-Mostrar";

        public static bool TestMode
        {
            get { return Environment.GetEnvironmentVariable("RADAR_NO_BROWSER") == "1"; }
        }

        [STAThread]
        static int Main(string[] args)
        {
            bool sair = Array.IndexOf(args, "--sair") >= 0;
            try { SetProcessDPIAware(); } catch (Exception) { }

            bool created;
            Mutex mutex = new Mutex(true, MutexName, out created);
            if (!created)
            {
                mutex.Dispose();  // senão esta cópia segura o "já estou aberto" da outra
                if (sair)
                {
                    SignalEvent(ExitEventName);
                    WaitOtherInstanceGone(30000);
                    Launcher.WaitPortsFree(10000);
                    Launcher.WaitWindowGone(10000);
                    return 0;
                }
                // Já aberto: traz a janela dele para a frente. Esta cópia foi aberta pela pessoa,
                // então pode passar a vez de ficar na frente para a outra.
                try { AllowSetForegroundWindow(-1); } catch (Exception) { }
                for (int i = 0; i < 20; i++)
                {
                    if (SignalEvent(ShowEventName)) return 0;
                    Thread.Sleep(100);  // a outra cópia pode estar começando agora
                }
                if (!TestMode) Launcher.OpenBrowser();
                return 0;
            }
            if (sair)
            {
                // Nenhum lançador aberto: fecha o que tiver sobrado nas portas do Radar 3D.
                Launcher.KillPorts();
                mutex.ReleaseMutex();
                return 0;
            }

            // Erro inesperado vai para o lancador.log, nunca para a caixa de erro do .NET.
            Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
            Application.ThreadException += delegate(object s, ThreadExceptionEventArgs e)
            {
                Launcher.Log("lancador.log", "erro: " + e.Exception);
            };
            AppDomain.CurrentDomain.UnhandledException += delegate(object s, UnhandledExceptionEventArgs e)
            {
                Launcher.Log("lancador.log", "erro fatal: " + e.ExceptionObject);
            };
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Launcher launcher = new Launcher();
            Application.Run(launcher);
            GC.KeepAlive(mutex);
            return launcher.ExitCode;
        }

        // Espera o outro lançador terminar de fechar (o "já estou aberto" some quando ele sai),
        // para o desinstalador não tentar apagar o .exe ainda em uso.
        static void WaitOtherInstanceGone(int timeoutMs)
        {
            DateTime limit = DateTime.Now.AddMilliseconds(timeoutMs);
            while (DateTime.Now < limit)
            {
                try
                {
                    Mutex other = Mutex.OpenExisting(MutexName);
                    other.Dispose();
                }
                catch (WaitHandleCannotBeOpenedException) { return; }
                catch (Exception) { return; }
                Thread.Sleep(250);
            }
        }

        static bool SignalEvent(string name)
        {
            try
            {
                EventWaitHandle ev;
                if (EventWaitHandle.TryOpenExisting(name, out ev))
                {
                    ev.Set();
                    ev.Dispose();
                    return true;
                }
            }
            catch (Exception) { }
            return false;
        }

        [DllImport("user32.dll")]
        static extern bool SetProcessDPIAware();

        [DllImport("user32.dll")]
        static extern bool AllowSetForegroundWindow(int processId);
    }

    // Cores do app (design.md), para as janelas combinarem com as telas.
    static class Palette
    {
        public static readonly Color Paper = Color.FromArgb(13, 9, 7);      // --color-paper
        public static readonly Color Ink = Color.FromArgb(240, 236, 230);   // --color-ink
        public static readonly Color Muted = Color.FromArgb(155, 149, 142);
    }

    sealed class Launcher : ApplicationContext
    {
        const int BackendPort = 8000;
        const int FrontendPort = 3000;
        const string Url = "http://localhost:3000/";

        static readonly string BaseDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Radar3D");
        static readonly string DataDir = Path.Combine(BaseDir, "data");
        static readonly string WebViewDir = Path.Combine(BaseDir, "webview");
        static readonly string WebViewPidFile = Path.Combine(BaseDir, "webview.pid");
        static readonly object LogLock = new object();

        readonly string app;       // pasta do programa (onde está este .exe)
        readonly Icon icon;
        readonly NotifyIcon tray;
        readonly SplashForm splash;
        readonly IntPtr job;
        readonly EventWaitHandle exitEvent;
        readonly EventWaitHandle showEvent;

        Process backend;
        Process frontend;
        Form window;               // a janela do app (AppWindow), quando aberta
        string lastUrl;            // tela que estava aberta quando a janela foi fechada
        bool useBrowser;           // sem WebView2: abre no navegador
        bool closeHintShown;
        int windowRestarts;
        volatile bool quitting;
        volatile bool ready;
        int backendRestarts;
        int frontendRestarts;
        public int ExitCode;

        public Launcher()
        {
            app = AppDomain.CurrentDomain.BaseDirectory;
            Directory.CreateDirectory(DataDir);
            job = JobObject.Create();
            exitEvent = new EventWaitHandle(false, EventResetMode.AutoReset, Program.ExitEventName);
            showEvent = new EventWaitHandle(false, EventResetMode.AutoReset, Program.ShowEventName);

            icon = LoadIcon();
            splash = new SplashForm(icon);
            tray = new NotifyIcon();
            tray.Icon = new Icon(icon, SystemInformation.SmallIconSize);
            tray.Text = "Radar 3D — abrindo…";
            tray.ContextMenuStrip = BuildMenu();
            tray.DoubleClick += delegate { ShowApp(); };
            tray.Visible = true;
            splash.Show();

            StartThread(WatchExitEvent);
            StartThread(WatchShowEvent);
            StartThread(Boot);
        }

        static void StartThread(ThreadStart work)
        {
            Thread t = new Thread(work);
            t.IsBackground = true;
            t.Start();
        }

        Icon LoadIcon()
        {
            // O .ico tem todos os tamanhos (16 a 256): fica nítido na barra de tarefas e no Alt+Tab.
            try
            {
                Icon ico = new Icon(Path.Combine(app, "radar3d.ico"));
                IntPtr ok = new Icon(ico, SystemInformation.SmallIconSize).Handle;  // lê mesmo (PNG)
                if (ok != IntPtr.Zero) return ico;
            }
            catch (Exception) { }
            try { return Icon.ExtractAssociatedIcon(Application.ExecutablePath); }
            catch (Exception) { return SystemIcons.Application; }
        }

        ContextMenuStrip BuildMenu()
        {
            ContextMenuStrip menu = new ContextMenuStrip();
            ToolStripMenuItem abrir = new ToolStripMenuItem("Abrir o Radar 3D");
            abrir.Font = new Font(abrir.Font, FontStyle.Bold);
            abrir.Click += delegate { ShowApp(); };
            ToolStripMenuItem pasta = new ToolStripMenuItem("Pasta dos dados e registros");
            pasta.Click += delegate { Process.Start("explorer.exe", "\"" + DataDir + "\""); };
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
            string venv = Path.Combine(BaseDir, "venv");
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
            string python = Path.Combine(BaseDir, "venv\\Scripts\\python.exe");
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
            info.EnvironmentVariables["RADAR_DATA_DIR"] = DataDir;
            info.EnvironmentVariables["UV_PYTHON_INSTALL_DIR"] = Path.Combine(BaseDir, "python");
            info.EnvironmentVariables["UV_PROJECT_ENVIRONMENT"] = Path.Combine(BaseDir, "venv");
            info.EnvironmentVariables["UV_CACHE_DIR"] = Path.Combine(BaseDir, "uv-cache");
            info.EnvironmentVariables["UV_PYTHON_PREFERENCE"] = "only-managed";
            info.EnvironmentVariables["UV_NO_PROGRESS"] = "1";
            info.EnvironmentVariables["PYTHONUTF8"] = "1";
            info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            info.EnvironmentVariables["PORT"] = FrontendPort.ToString();
            info.EnvironmentVariables["HOSTNAME"] = "127.0.0.1";
            info.EnvironmentVariables["NODE_ENV"] = "production";

            string logPath = Path.Combine(DataDir, logName);
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
            RunOnUi(delegate
            {
                ready = true;
                tray.Text = "Radar 3D";
                string missing = WebViewMissing();
                if (missing == null)
                {
                    ShowWindow();
                    splash.Hide();
                    return;
                }
                Log("lancador.log", "Sem a janela própria (" + missing + "): abrindo no navegador.");
                UseBrowser();
            });
        }

        // ---------------------------------------------------------------- a janela do app

        // Nulo quando dá para abrir a janela própria; senão, o motivo (vai para o log).
        string WebViewMissing()
        {
            foreach (string dll in new string[] { "Microsoft.Web.WebView2.Core.dll", "Microsoft.Web.WebView2.WinForms.dll" })
            {
                if (!File.Exists(Path.Combine(app, dll))) return "faltou " + dll;
            }
            try
            {
                string version = WebViewVersion();
                if (string.IsNullOrEmpty(version)) return "WebView2 não instalado";
                Log("lancador.log", "WebView2 " + version);
                return null;
            }
            catch (Exception ex) { return ex.GetType().Name + ": " + ex.Message; }
        }

        // Separado (e fora de linha) para a falta das DLLs do WebView2 virar só uma exceção aqui.
        [MethodImpl(MethodImplOptions.NoInlining)]
        static string WebViewVersion()
        {
            return CoreWebView2Environment.GetAvailableBrowserVersionString();
        }

        // Abrir pelo atalho, pelo ícone ou de novo pelo menu Iniciar: mostra o que já está aberto.
        void ShowApp()
        {
            if (quitting) return;
            if (!ready)
            {
                splash.Show();
                splash.Activate();
                return;
            }
            if (!useBrowser) ShowWindow();
            else if (!Program.TestMode) OpenBrowser();
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        void ShowWindow()
        {
            AppWindow w = window as AppWindow;
            if (w == null || w.IsDisposed)
            {
                w = new AppWindow(icon, WebViewDir, lastUrl ?? Url);
                w.Log = delegate(string line) { Log("lancador.log", line); };
                w.Failed = OnWindowFailed;
                w.BrowserStarted = delegate(int pid) { WriteWebViewPid(pid); };
                w.FormClosed += delegate { OnWindowClosed(w.LastUrl, w.FailedToOpen, w.Recreating); };
                window = w;
            }
            w.ShowOnTop();
        }

        void OnWindowClosed(string url, bool failed, bool recreate)
        {
            window = null;
            if (url != null) lastUrl = url;
            if (quitting || failed) return;
            if (recreate && ++windowRestarts <= 3)
            {
                RunOnUi(ShowWindow);
                return;
            }
            if (!closeHintShown)
            {
                // Fechar a janela deixa a coleta seguindo; conta uma vez como abrir e sair.
                closeHintShown = true;
                tray.ShowBalloonTip(10000, "O Radar 3D continua aberto",
                    "Ele segue coletando as tendências aqui perto do relógio. Para abrir de novo: dois cliques " +
                    "no ícone. Para fechar de vez: botão direito no ícone → Sair.", ToolTipIcon.Info);
            }
        }

        void OnWindowFailed(string reason)
        {
            if (quitting) return;
            Log("lancador.log", "Sem a janela própria (" + reason + "): abrindo no navegador.");
            UseBrowser();
        }

        void UseBrowser()
        {
            useBrowser = true;
            splash.Hide();
            tray.ShowBalloonTip(8000, "Radar 3D aberto",
                "Ele abriu no navegador e fica aqui perto do relógio. Para fechar: botão direito no ícone → Sair.",
                ToolTipIcon.Info);
            if (!Program.TestMode) OpenBrowser();
        }

        static void WriteWebViewPid(int pid)
        {
            try { File.WriteAllText(WebViewPidFile, pid.ToString()); } catch (Exception) { }
        }

        // Espera o WebView2 da janela terminar de fechar (libera a pasta webview para o
        // desinstalador).
        public static void WaitWindowGone(int timeoutMs)
        {
            try
            {
                if (!File.Exists(WebViewPidFile)) return;
                int pid = int.Parse(File.ReadAllText(WebViewPidFile).Trim());
                Process p = Process.GetProcessById(pid);
                if (p.ProcessName.StartsWith("msedgewebview2", StringComparison.OrdinalIgnoreCase)) p.WaitForExit(timeoutMs);
            }
            catch (Exception) { }
        }

        // ---------------------------------------------------------------- se uma parte cair

        void OnChildExited(bool isBackend)
        {
            try
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
            catch (Exception ex) { Log("lancador.log", "erro ao reiniciar: " + ex); }
        }

        // ---------------------------------------------------------------- sair

        void WatchExitEvent()
        {
            exitEvent.WaitOne();
            RunOnUi(Quit);
        }

        void WatchShowEvent()
        {
            while (true)
            {
                showEvent.WaitOne();
                RunOnUi(ShowApp);
            }
        }

        void Quit()
        {
            quitting = true;
            if (window != null && !window.IsDisposed) window.Close();
            KillTree(frontend);
            KillTree(backend);
            KillPorts();
            tray.Visible = false;
            tray.Dispose();
            splash.AllowClose = true;
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
            List<int> pids = new List<int>();
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
            foreach (IPEndPoint ep in IPGlobalProperties.GetIPGlobalProperties().GetActiveTcpListeners())
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
            if (Program.TestMode)
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
                    try { Process.Start("notepad.exe", "\"" + Path.Combine(DataDir, logName) + "\""); } catch (Exception) { }
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

        public static void Log(string logName, string line)
        {
            lock (LogLock)
            {
                try
                {
                    Directory.CreateDirectory(DataDir);
                    File.AppendAllText(Path.Combine(DataDir, logName), line + Environment.NewLine, Encoding.UTF8);
                }
                catch (Exception) { }
            }
        }
    }

    // A janela do Radar 3D: as telas (servidas em localhost:3000) dentro de um WebView2, sem nada
    // de navegador em volta. Links para fora (lojas, Google AI Studio…) abrem no navegador padrão.
    // Fechar a janela libera o WebView2 (memória); abrir de novo cria outra na mesma tela.
    sealed class AppWindow : Form
    {
        // Itens de navegador tirados do menu do botão direito (ficam copiar, colar, emoji…).
        static readonly string[] BrowserMenuItems = {
            "back", "forward", "reload", "saveAs", "print", "share", "webCapture", "createQrCode",
            "inspectElement", "openLinkInNewWindow", "saveLinkAs", "copyLinkToHighlight"
        };

        static readonly CoreWebView2WebErrorStatus[] ConnectionErrors = {
            CoreWebView2WebErrorStatus.CannotConnect, CoreWebView2WebErrorStatus.ConnectionAborted,
            CoreWebView2WebErrorStatus.ConnectionReset, CoreWebView2WebErrorStatus.Disconnected,
            CoreWebView2WebErrorStatus.ServerUnreachable, CoreWebView2WebErrorStatus.Timeout,
            CoreWebView2WebErrorStatus.ErrorHttpInvalidServerResponse
        };

        readonly WebView2 web;
        readonly string userDataFolder;
        readonly string startUrl;
        string lastLocalUrl;
        bool loadedOnce;
        bool failing;
        FormWindowState restoreState = FormWindowState.Maximized;

        public Action<string> Log;
        public Action<string> Failed;
        public Action<int> BrowserStarted;
        public string LastUrl;
        public bool FailedToOpen;
        public bool Recreating;

        public AppWindow(Icon icon, string userDataFolder, string startUrl)
        {
            this.userDataFolder = userDataFolder;
            this.startUrl = startUrl;
            lastLocalUrl = startUrl;

            Text = "Radar 3D";
            Icon = icon;
            BackColor = Palette.Paper;
            MinimumSize = new Size(640, 480);
            StartPosition = FormStartPosition.Manual;
            Rectangle area = Screen.PrimaryScreen.WorkingArea;
            Size = new Size(area.Width * 9 / 10, area.Height * 9 / 10);
            Location = new Point(area.X + (area.Width - Width) / 2, area.Y + (area.Height - Height) / 2);
            WindowState = FormWindowState.Maximized;

            web = new WebView2();
            web.Dock = DockStyle.Fill;
            web.DefaultBackgroundColor = Palette.Paper;  // sem clarão branco enquanto a tela carrega
            Controls.Add(web);
        }

        public void ShowOnTop()
        {
            if (!Visible) Show();
            if (WindowState == FormWindowState.Minimized) WindowState = restoreState;
            Activate();
            SetForegroundWindow(Handle);
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            TitleBar.Dark(Handle);
        }

        protected override void OnResize(EventArgs e)
        {
            base.OnResize(e);
            if (WindowState != FormWindowState.Minimized) restoreState = WindowState;
        }

        protected override async void OnLoad(EventArgs e)
        {
            base.OnLoad(e);
            try
            {
                CoreWebView2Environment env = await CoreWebView2Environment.CreateAsync(null, userDataFolder, null);
                if (IsDisposed) return;
                await web.EnsureCoreWebView2Async(env);
            }
            catch (Exception ex)
            {
                if (IsDisposed) return;
                FailedToOpen = true;
                if (Failed != null) Failed(ex.GetType().Name + ": " + ex.Message);
                BeginInvoke((MethodInvoker)Close);
                return;
            }
            try
            {
                if (IsDisposed) return;
                Setup(web.CoreWebView2);
                web.CoreWebView2.Navigate(startUrl);
                web.Focus();
            }
            catch (Exception ex) { Write("janela: " + ex.Message); }
        }

        void Setup(CoreWebView2 core)
        {
            CoreWebView2Settings s = core.Settings;
            s.AreDevToolsEnabled = Environment.GetEnvironmentVariable("RADAR_DEVTOOLS") == "1";
            s.IsStatusBarEnabled = false;  // sem "http://localhost:3000/…" no canto ao passar nos links
            try { s.IsPasswordAutosaveEnabled = false; } catch (Exception) { }  // a chave do Gemini não vira "senha salva"
            try { s.IsGeneralAutofillEnabled = false; } catch (Exception) { }
            core.NavigationStarting += OnNavigationStarting;
            core.NewWindowRequested += OnNewWindowRequested;
            core.NavigationCompleted += OnNavigationCompleted;
            core.ProcessFailed += OnProcessFailed;
            try { core.ContextMenuRequested += OnContextMenuRequested; } catch (Exception) { }
            try { if (BrowserStarted != null) BrowserStarted((int)core.BrowserProcessId); } catch (Exception) { }
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            try
            {
                string current = web.CoreWebView2 != null ? web.CoreWebView2.Source : null;
                LastUrl = IsAppPage(current) ? current : lastLocalUrl;
            }
            catch (Exception) { LastUrl = lastLocalUrl; }
            base.OnFormClosing(e);
        }

        // Telas do Radar 3D (e as páginas internas de reconexão): ficam na janela.
        static bool IsAppPage(string uri)
        {
            Uri u;
            if (uri == null || !Uri.TryCreate(uri, UriKind.Absolute, out u)) return false;
            return u.Scheme == Uri.UriSchemeHttp && u.Port == 3000 && (u.Host == "localhost" || u.Host == "127.0.0.1");
        }

        static bool IsInternal(string uri)
        {
            return uri != null && (uri.StartsWith("about:") || uri.StartsWith("data:"));
        }

        void OnNavigationStarting(object sender, CoreWebView2NavigationStartingEventArgs e)
        {
            if (IsAppPage(e.Uri)) { lastLocalUrl = e.Uri; return; }
            if (IsInternal(e.Uri)) return;
            e.Cancel = true;
            OpenOutside(e.Uri);
        }

        void OnNewWindowRequested(object sender, CoreWebView2NewWindowRequestedEventArgs e)
        {
            // Nada de janelas extras: tela do app abre aqui mesmo; site de fora, no navegador.
            e.Handled = true;
            if (IsAppPage(e.Uri)) web.CoreWebView2.Navigate(e.Uri);
            else OpenOutside(e.Uri);
        }

        static void OpenOutside(string uri)
        {
            Uri u;
            if (!Uri.TryCreate(uri, UriKind.Absolute, out u)) return;
            if (u.Scheme != Uri.UriSchemeHttp && u.Scheme != Uri.UriSchemeHttps && u.Scheme != Uri.UriSchemeMailto) return;
            try
            {
                ProcessStartInfo info = new ProcessStartInfo(u.AbsoluteUri);
                info.UseShellExecute = true;
                Process.Start(info);
            }
            catch (Exception) { }
        }

        async void OnNavigationCompleted(object sender, CoreWebView2NavigationCompletedEventArgs e)
        {
            try
            {
                CoreWebView2 core = web.CoreWebView2;
                if (!e.IsSuccess)
                {
                    // Só falha de conexão (404 e afins o próprio app mostra; cancelada é nossa).
                    if (Array.IndexOf(ConnectionErrors, e.WebErrorStatus) < 0) return;
                    // As telas estão reiniciando (o lançador sobe de novo sozinho): em vez da página
                    // de erro do Edge, um aviso que tenta de novo a cada 3 segundos.
                    if (!failing) Write("janela: não carregou " + lastLocalUrl + " (" + e.WebErrorStatus + ")");
                    failing = true;
                    core.NavigateToString(ReconnectPage(lastLocalUrl));
                    return;
                }
                if (!IsAppPage(core.Source)) return;
                failing = false;
                if (loadedOnce) return;
                loadedOnce = true;
                string chars = await core.ExecuteScriptAsync("document.body ? document.body.innerText.length : 0");
                Write("janela carregou: " + core.DocumentTitle + " (" + chars + " caracteres na tela)");
            }
            catch (Exception) { }
        }

        static string ReconnectPage(string target)
        {
            return "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><title>Radar 3D</title>" +
                "<meta http-equiv=\"refresh\" content=\"3;url=" + WebUtility.HtmlEncode(target) + "\"></head>" +
                "<body style=\"margin:0;height:100vh;display:flex;align-items:center;justify-content:center;" +
                "background:#0d0907;color:#f0ece6;font:16px 'Segoe UI',sans-serif;text-align:center\">" +
                "<div><p style=\"font-size:22px;margin:0 0 10px\">Reconectando…</p>" +
                "<p style=\"margin:0;color:#9b958e\">Uma parte do Radar 3D está reiniciando. " +
                "Esta tela volta sozinha em alguns segundos.</p></div></body></html>";
        }

        void OnProcessFailed(object sender, CoreWebView2ProcessFailedEventArgs e)
        {
            Write("janela: processo do WebView2 falhou (" + e.ProcessFailedKind + ")");
            if (e.ProcessFailedKind == CoreWebView2ProcessFailedKind.BrowserProcessExited)
            {
                // O WebView2 inteiro caiu: o lançador abre uma janela nova.
                Recreating = true;
                BeginInvoke((MethodInvoker)Close);
            }
            else if (e.ProcessFailedKind == CoreWebView2ProcessFailedKind.RenderProcessExited)
            {
                try { web.Reload(); } catch (Exception) { }
            }
        }

        void OnContextMenuRequested(object sender, CoreWebView2ContextMenuRequestedEventArgs e)
        {
            IList<CoreWebView2ContextMenuItem> items = e.MenuItems;
            for (int i = items.Count - 1; i >= 0; i--)
            {
                if (Array.IndexOf(BrowserMenuItems, items[i].Name) >= 0) items.RemoveAt(i);
            }
            // Separadores que sobraram nas pontas ou repetidos.
            for (int i = items.Count - 1; i >= 0; i--)
            {
                if (items[i].Kind != CoreWebView2ContextMenuItemKind.Separator) continue;
                if (i == 0 || i == items.Count - 1 || items[i - 1].Kind == CoreWebView2ContextMenuItemKind.Separator)
                {
                    items.RemoveAt(i);
                }
            }
            if (items.Count == 0) e.Handled = true;  // clique direito no vazio: nenhum menu
        }

        void Write(string line)
        {
            if (Log != null) Log(line);
        }

        [DllImport("user32.dll")]
        static extern bool SetForegroundWindow(IntPtr hwnd);
    }

    sealed class SplashForm : Form
    {
        readonly Label status;
        readonly Label detail;
        public bool AllowClose;

        public SplashForm(Icon icon)
        {
            SuspendLayout();
            // Medidas em 96 dpi; o Windows aumenta tudo junto em telas com zoom (125%, 150%…).
            AutoScaleDimensions = new SizeF(96F, 96F);
            AutoScaleMode = AutoScaleMode.Dpi;
            Text = "Radar 3D";
            Icon = icon;
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(480, 184);
            BackColor = Palette.Paper;
            ForeColor = Palette.Ink;
            Font = new Font("Segoe UI", 10f);
            ShowInTaskbar = true;

            PictureBox logo = new PictureBox();
            try { logo.Image = new Icon(icon, 64, 64).ToBitmap(); } catch (Exception) { }
            logo.SizeMode = PictureBoxSizeMode.Zoom;
            logo.SetBounds(20, 22, 56, 56);

            Label title = new Label();
            title.Text = "Radar 3D";
            title.Font = new Font("Segoe UI Semibold", 16f);
            title.AutoSize = true;
            title.Location = new Point(92, 20);

            status = new Label();
            status.Text = "Abrindo o Radar 3D…";
            status.SetBounds(92, 58, 368, 58);

            ProgressBar bar = new ProgressBar();
            bar.Style = ProgressBarStyle.Marquee;
            bar.MarqueeAnimationSpeed = 30;
            bar.SetBounds(20, 124, 440, 8);

            detail = new Label();
            detail.ForeColor = Palette.Muted;
            detail.Font = new Font("Segoe UI", 8.5f);
            detail.AutoEllipsis = true;
            detail.SetBounds(20, 142, 440, 32);

            Controls.Add(logo);
            Controls.Add(title);
            Controls.Add(status);
            Controls.Add(bar);
            Controls.Add(detail);
            ResumeLayout(false);
            PerformLayout();
        }

        public void SetStatus(string text) { status.Text = text; }

        public void SetDetail(string text) { detail.Text = text; }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            TitleBar.Dark(Handle);
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            // Fechar a janelinha não fecha o Radar 3D: ele segue abrindo e fica perto do relógio.
            if (!AllowClose && e.CloseReason == CloseReason.UserClosing)
            {
                e.Cancel = true;
                Hide();
                return;
            }
            base.OnFormClosing(e);
        }
    }

    // Barra de título escura como as telas (Windows 10 20H1+ e 11; no 11, da cor exata do fundo).
    static class TitleBar
    {
        const int DarkMode = 20;
        const int DarkModeOld = 19;  // Windows 10 1809 a 1909
        const int CaptionColor = 35;

        [DllImport("dwmapi.dll")]
        static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);

        public static void Dark(IntPtr hwnd)
        {
            try
            {
                int on = 1;
                if (DwmSetWindowAttribute(hwnd, DarkMode, ref on, 4) != 0) DwmSetWindowAttribute(hwnd, DarkModeOld, ref on, 4);
                Color c = Palette.Paper;
                int colorRef = c.R | (c.G << 8) | (c.B << 16);
                DwmSetWindowAttribute(hwnd, CaptionColor, ref colorRef, 4);
            }
            catch (Exception) { }
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
