#!/usr/bin/env node
// Deterministic protected-region checker for EN->ZH translation output.
// Usage: node validate-output.mjs <source> <target> [--verbose] [--expect-sha256 <hash>]
// Exit 0 = passed, 1 = protected-region mismatch, 2 = usage/IO error, 3 = source drifted from snapshot.
import fs from 'node:fs';
import crypto from 'node:crypto';
const argv = process.argv.slice(2);
const verbose = argv.includes('--verbose');
const shaIdx = argv.indexOf('--expect-sha256');
const expectSha = shaIdx >= 0 ? argv[shaIdx + 1] : null;
const pos = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--verbose') continue;
  if (argv[i] === '--expect-sha256') { i++; continue; }
  pos.push(argv[i]);
}
const [source, target] = pos;
if (!source || !target || (shaIdx >= 0 && !expectSha)) { console.error(JSON.stringify({ status: 'error', reason: 'usage: validate-output.mjs <source> <target> [--verbose] [--expect-sha256 <hash>]' })); process.exit(2); }
let s, t, sourceBytes;
try { sourceBytes = fs.readFileSync(source); s = sourceBytes.toString('utf8'); t = fs.readFileSync(target, 'utf8'); }
catch (e) { console.error(JSON.stringify({ status: 'error', reason: `cannot read file: ${e.code || e.message}` })); process.exit(2); }

// Source drift check: the file hashed by inspect-source.mjs before translation must still match.
if (expectSha) {
  const actual = crypto.createHash('sha256').update(sourceBytes).digest('hex');
  if (actual !== expectSha) {
    console.error(JSON.stringify({ status: 'source-drift', reason: `source sha256 ${actual} != expected ${expectSha}; re-snapshot and re-translate` }));
    process.exit(3);
  }
}

// CommonMark fences: up to 3 spaces of indent; a fence is closed only by a
// same-character line of at least the opening length, so nested shorter fences
// stay inside the protected block instead of truncating it.
function scanFences(x) {
  const out = []; const lines = x.split('\n');
  let i = 0;
  while (i < lines.length) {
    const m = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(lines[i]);
    if (m && (m[1][0] === '~' || !m[2].includes('`'))) {
      const marker = m[1][0]; const len = m[1].length;
      const closeRe = new RegExp(`^ {0,3}\\${marker}{${len},}\\s*$`);
      let j = i + 1; let end = lines.length - 1;
      while (j < lines.length) { if (closeRe.test(lines[j])) { end = j; break; } j++; }
      out.push(lines.slice(i, end + 1).join('\n'));
      i = end + 1; continue;
    }
    i++;
  }
  return out;
}

// Inline $...$ counts as a formula only when LaTeX-like: no space hugging the
// delimiters and either a single token or a math construct char. Keeps "$5 and
// $10" (currency prose) out of the protected set.
const latexLike = (f) => { const c = f.slice(1, -1); return !/^\s|\s$/.test(c) && (!/\s/.test(c) || /[\\^_{}]/.test(c)); };
const stripTrailingPunct = (u) => u.replace(/[.,;:!?)\]。。；：！？）】》]+$/, '');
const structureMarker = (l) => { const m = /^ {0,3}((?:#{1,6})\s|(?:[-*+] |\d+\. )|> ?)/.exec(l); return m ? m[1].trim() : null; };

const protectedParts = (x) => ({
  fences: scanFences(x),
  inline: [...x.matchAll(/`[^`\n]+`/g)].map(m => m[0]),
  displayFormulas: [...x.matchAll(/\$\$[\s\S]+?\$\$/g)].map(m => m[0]),
  inlineFormulas: [...x.matchAll(/\$[^$\n]+\$/g)].map(m => m[0]).filter(latexLike),
  urls: [...x.matchAll(/(?:https?|ftp):\/\/[^\s\u3400-\u9fff\u3000-\u303f\uff00-\uffef<>()\[\]]+/g)].map(m => stripTrailingPunct(m[0])),
  refdefs: x.split('\n').filter(l => /^ {0,3}\[[^\]]+\]:\s*\S/.test(l)),
  links: [...x.matchAll(/!?\[[^\]]*\]\(([^()]*(?:\([^()]*\)[^()]*)*)\)/g)].map(m => m[1]),
  placeholders: [...x.matchAll(/\{\{[^}]+\}\}|<%[^%]+%>/g)].map(m => m[0]),
  images: [...x.matchAll(/!\[[^\]]*\]\(([^()]*(?:\([^()]*\)[^()]*)*)\)/g)].map(m => m[1]),
  html: [...x.matchAll(/<\/?[A-Za-z][^>]*>/g)].map(m => m[0]),
  structure: x.split('\n').map(structureMarker).filter(Boolean),
  frontmatter: x.startsWith('---\n') ? (x.match(/^---\n[\s\S]*?\n(?:---|\.\.\.)\n/) || [''])[0] : ''
});

const a = protectedParts(s), b = protectedParts(t);
// Emphasis-adjacent-CJK spacing is a target-side formatting rule; require CJK
// inside the emphasis so bare identifiers like __init__ are never flagged.
const emphasisIssues = [...t.matchAll(/(\*\*|__|\*)([^*\n]+?)\1(?=[\u3400-\u9fff])/g)].filter(m => /[\u3400-\u9fff]/.test(m[2]));
const ok = JSON.stringify(a) === JSON.stringify(b) && emphasisIssues.length === 0;
const counts = {};
for (const k of Object.keys(a)) counts[k] = { source: Array.isArray(a[k]) ? a[k].length : (a[k] ? 1 : 0), target: Array.isArray(b[k]) ? b[k].length : (b[k] ? 1 : 0) };
const formatIssues = emphasisIssues.length ? ['emphasis must be followed by a space before CJK text'] : [];
const report = ok ? { status: 'passed', counts, format_issues: formatIssues } : { status: 'failed', counts, format_issues: formatIssues, diff: { source: a, target: b } };
if (verbose) report.detail = { source: a, target: b };
console.log(JSON.stringify(report));
process.exit(ok ? 0 : 1);
