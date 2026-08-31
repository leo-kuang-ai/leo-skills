#!/usr/bin/env node
/**
 * rasterize_svg.mjs — SVG → PNG 的 Node 备选栅格化子进程（设计 §3.3.1）。
 *
 * 协议：stdin 一行 JSON → stdout 一行 JSON。与 Python 调用方
 * (runtime/src/leo_ppt_generator/render/raster.py) 之间只有本协议，无共享
 * 状态；本脚本永不进 PPTX 组装路径（CI-6）。
 *
 * 输入字段：
 *   svg_path | svg_string   二选一
 *   out_path                PNG 输出路径
 *   width                   fitTo width（缺省 2560）
 *   background              显式背景色（缺省 #ffffff，不透明）
 *   font_dirs[]             显式字体目录（loadSystemFonts=false，位级确定前提）
 *   default_font_family     缺省字族
 *
 * 输出：{ok:true, out, width, height} 或 {ok:false, error}
 *
 * 依赖：@resvg/resvg-js（从 CWD/node_modules 解析）。缺依赖时输出
 * {ok:false, error:"module_unavailable"}，由调用方归入
 * rasterizer_unavailable。
 */
import { createRequire } from "node:module";
import { writeFileSync } from "node:fs";

const require = createRequire(import.meta.url);

function emit(value) {
  process.stdout.write(JSON.stringify(value) + "\n");
}

function readStdin() {
  return new Promise((resolve, reject) => {
    let buffer = "";
    process.stdin.setEncoding("utf-8");
    process.stdin.on("data", (chunk) => (buffer += chunk));
    process.stdin.on("end", () => resolve(buffer));
    process.stdin.on("error", reject);
  });
}

let Resvg;
try {
  ({ Resvg } = require("@resvg/resvg-js"));
} catch (error) {
  emit({ ok: false, error: `module_unavailable: ${error && error.code ? error.code : String(error)}` });
  process.exit(0);
}

let payload;
try {
  const raw = await readStdin();
  payload = JSON.parse(raw.trim().split("\n").pop() || "{}");
} catch (error) {
  emit({ ok: false, error: `stdin_json_invalid: ${String(error)}` });
  process.exit(0);
}

try {
  const svg = payload.svg_path
    ? await (await import("node:fs/promises")).readFile(payload.svg_path, "utf-8")
    : payload.svg_string;
  if (!svg || !String(svg).includes("<svg")) {
    throw new Error("svg_input_invalid");
  }
  const opts = {
    fitTo: { mode: "width", value: Number(payload.width) || 2560 },
    background: String(payload.background || "#ffffff"),
    font: {
      loadSystemFonts: false,
      fontDirs: Array.isArray(payload.font_dirs) ? payload.font_dirs : [],
      defaultFontFamily: String(payload.default_font_family || "Noto Sans SC"),
    },
  };
  const resvg = new Resvg(svg, opts);
  const png = resvg.render().asPng();
  const size = resvg.getBBox();
  writeFileSync(payload.out_path, png);
  emit({
    ok: true,
    out: payload.out_path,
    width: Math.round(size.width),
    height: Math.round(size.height),
  });
} catch (error) {
  emit({ ok: false, error: String(error && error.message ? error.message : error).slice(0, 300) });
}
