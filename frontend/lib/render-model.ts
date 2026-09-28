// Tira 4 fotos (renders) de um arquivo 3D no próprio computador, para a IA analisar o modelo
// como se fossem renders enviados pela pessoa. Este módulo (com o three.js) só é baixado quando
// alguém escolhe um arquivo 3D.
//
// - STL e 3MF são arquivos de impressão, em pé no eixo Z: giram para ficar em pé aqui (Y).
// - STL, 3MF, OBJ e FBX viram "argila" clara (as texturas deles ficam em arquivos separados, e
//   a cor de impressão não diz nada da escultura); GLB mantém os materiais dele.
// - Capa em 3/4 (o ângulo que mais vende), depois frente, lado e costas.

import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { ThreeMFLoader } from "three/examples/jsm/loaders/3MFLoader.js";
import { modelExtension } from "@/lib/model-files";

const MAX_BYTES = 250 * 1024 * 1024;
const FOV = 30;
const MARGIN = 0.86; // o modelo ocupa até 86% da foto
const SIZE = 1200;
const BACKGROUND = 0x1d1a18;
const CLAY = 0xaea59a;

export const VIEWS = [
  { name: "capa", label: "capa em 3/4", azimuth: 35, elevation: 18 },
  { name: "frente", label: "frente", azimuth: 0, elevation: 6 },
  { name: "lado", label: "lado", azimuth: 90, elevation: 6 },
  { name: "costas", label: "costas", azimuth: 180, elevation: 12 },
] as const;

export class ModelRenderError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ModelRenderError"; // a tela mostra a mensagem só destes erros
  }
}

const MSG_OPEN =
  "Não consegui abrir esse arquivo 3D. Exporte em STL, OBJ ou GLB, ou envie prints do modelo.";
const MSG_WEBGL =
  "Este computador não conseguiu desenhar o modelo 3D. Envie prints ou renders do modelo.";

type Loaded = { object: THREE.Object3D; keepMaterials: boolean; zUp: boolean };

async function load(ext: string, buffer: ArrayBuffer): Promise<Loaded> {
  switch (ext) {
    case "stl":
      return { object: new THREE.Mesh(new STLLoader().parse(buffer)), keepMaterials: false, zUp: true };
    case "3mf":
      return { object: new ThreeMFLoader().parse(buffer), keepMaterials: false, zUp: true };
    case "obj":
      return { object: new OBJLoader().parse(new TextDecoder().decode(buffer)), keepMaterials: false, zUp: false };
    case "fbx":
      return { object: new FBXLoader().parse(buffer, ""), keepMaterials: false, zUp: false };
    case "glb":
      return { object: (await new GLTFLoader().parseAsync(buffer, "")).scene, keepMaterials: true, zUp: false };
    default:
      throw new ModelRenderError(MSG_OPEN);
  }
}

function dispose(object: THREE.Object3D) {
  object.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.geometry?.dispose();
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    materials.forEach((material) => material?.dispose());
  });
}

// Até ~20 mil pontos da malha (já na posição final), para enquadrar pela forma de verdade e não
// pela caixa em volta (que num ângulo de 3/4 deixaria o modelo pequeno na foto).
function samplePoints(object: THREE.Object3D, limit = 20_000): THREE.Vector3[] {
  const meshes: THREE.Mesh[] = [];
  let total = 0;
  object.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (mesh.isMesh && mesh.geometry.attributes.position) {
      meshes.push(mesh);
      total += mesh.geometry.attributes.position.count;
    }
  });
  const step = Math.max(1, Math.ceil(total / limit));
  const points: THREE.Vector3[] = [];
  for (const mesh of meshes) {
    const position = mesh.geometry.attributes.position;
    for (let i = 0; i < position.count; i += step) {
      points.push(new THREE.Vector3().fromBufferAttribute(position, i).applyMatrix4(mesh.matrixWorld));
    }
  }
  return points;
}

// Distância da câmera (olhando para o centro, na direção dada) em que todos os pontos cabem na
// foto: enquadra justo em qualquer ângulo.
function fitDistance(points: THREE.Vector3[], direction: THREE.Vector3): number {
  const back = direction.clone().normalize();
  const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), back).normalize();
  const up = new THREE.Vector3().crossVectors(back, right);
  const tan = Math.tan(THREE.MathUtils.degToRad(FOV / 2)) * MARGIN;
  let distance = 0;
  for (const point of points) {
    const depth = point.dot(back);
    distance = Math.max(distance, depth + Math.abs(point.dot(right)) / tan, depth + Math.abs(point.dot(up)) / tan);
  }
  return distance;
}

export async function renderModel(file: File): Promise<File[]> {
  const ext = modelExtension(file);
  if (!ext) throw new ModelRenderError(MSG_OPEN);
  if (file.size > MAX_BYTES) {
    throw new ModelRenderError("Esse arquivo 3D passa de 250 MB. Envie prints ou renders do modelo.");
  }

  let loaded: Loaded;
  try {
    loaded = await load(ext, await file.arrayBuffer());
  } catch {
    throw new ModelRenderError(MSG_OPEN);
  }
  const { object, keepMaterials, zUp } = loaded;

  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  } catch {
    dispose(object);
    throw new ModelRenderError(MSG_WEBGL);
  }

  const pmrem = new THREE.PMREMGenerator(renderer);
  const environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  const clay = new THREE.MeshStandardMaterial({ color: CLAY, roughness: 0.6, metalness: 0 });
  try {
    renderer.setPixelRatio(1);
    renderer.setSize(SIZE, SIZE, false);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(BACKGROUND);
    scene.environment = environment;

    if (!keepMaterials) {
      object.traverse((child) => {
        const mesh = child as THREE.Mesh;
        if (mesh.isMesh) mesh.material = clay;
      });
    }
    if (zUp) object.rotation.x = -Math.PI / 2;
    object.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(object);
    if (box.isEmpty()) throw new ModelRenderError(MSG_OPEN);
    object.position.sub(box.getCenter(new THREE.Vector3()));
    scene.add(object);
    const radius = box.getBoundingSphere(new THREE.Sphere()).radius || 1;

    // Luzes presas à câmera: todo ângulo sai iluminado do mesmo jeito. Luz principal de cima e
    // da esquerda para marcar o volume; contraluz quente para separar do fundo escuro.
    scene.environmentIntensity = 0.35;
    const camera = new THREE.PerspectiveCamera(FOV, 1, radius / 100, radius * 100);
    const key = new THREE.DirectionalLight(0xffffff, 2.8);
    key.position.set(-1, 1.4, 0.8);
    const rim = new THREE.DirectionalLight(0xffd6a8, 1.6);
    rim.position.set(1.4, 0.8, -1.6);
    camera.add(key, key.target, rim, rim.target);
    key.target.position.set(0, 0, -1);
    rim.target.position.set(0, 0, -1);
    scene.add(camera);
    object.updateMatrixWorld(true);
    const points = samplePoints(object);

    const base = file.name.replace(/\.[^.]+$/, "");
    const files: File[] = [];
    for (const view of VIEWS) {
      const azimuth = THREE.MathUtils.degToRad(view.azimuth);
      const elevation = THREE.MathUtils.degToRad(view.elevation);
      const direction = new THREE.Vector3(
        Math.cos(elevation) * Math.sin(azimuth),
        Math.sin(elevation),
        Math.cos(elevation) * Math.cos(azimuth),
      );
      camera.position.copy(direction.multiplyScalar(fitDistance(points, direction)));
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
      const blob = await new Promise<Blob | null>((resolve) => renderer.domElement.toBlob(resolve, "image/png"));
      if (!blob) throw new ModelRenderError(MSG_WEBGL);
      files.push(new File([blob], `${base}-${view.name}.png`, { type: "image/png" }));
    }
    return files;
  } finally {
    dispose(object);
    clay.dispose();
    environment.dispose();
    pmrem.dispose();
    renderer.dispose();
    renderer.forceContextLoss();
  }
}
