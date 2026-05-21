import { cp, mkdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const distDir = path.join(__dirname, "dist");
const assets = [
  "index.html",
  "dashboard.html",
  "simulator.html",
  "walker.html",
  "traps.html",
  "browser.html",
  "mibs.html",
  "settings.html",
  "css",
  "js",
  "img",
  "favicon.ico",
];

async function exists(target) {
  try {
    await stat(target);
    return true;
  } catch {
    return false;
  }
}

async function copyAsset(asset) {
  const source = path.join(__dirname, asset);
  if (!(await exists(source))) {
    return;
  }

  const destination = path.join(distDir, asset);
  await mkdir(path.dirname(destination), { recursive: true });
  await cp(source, destination, { recursive: true });
}

async function build() {
  await rm(distDir, { recursive: true, force: true });
  await mkdir(distDir, { recursive: true });

  for (const asset of assets) {
    await copyAsset(asset);
  }
}

build().catch((error) => {
  console.error("Frontend build failed.");
  console.error(error);
  process.exitCode = 1;
});
