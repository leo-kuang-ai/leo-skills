#!/usr/bin/env node
// Snapshot a source file (sha256 + bytes + kind) before translation.
import fs from 'node:fs'; import crypto from 'node:crypto';
const p = process.argv[2]; if (!p) { console.error('source path required'); process.exit(2); }
let b; try { b = fs.readFileSync(p); } catch (e) { console.error(`cannot read source file ${p}: ${e.code || e.message}`); process.exit(2); }
const out = { source_sha256: crypto.createHash('sha256').update(b).digest('hex'), bytes: b.length, source_kind: /\.(md|markdown|mdx)$/.test(p) ? 'markdown' : 'text' };
if (b.length > 10 * 1024 * 1024) out.size_warning = 'file exceeds 10 MB; prefer chunked translation with a shared session glossary';
console.log(JSON.stringify(out));
