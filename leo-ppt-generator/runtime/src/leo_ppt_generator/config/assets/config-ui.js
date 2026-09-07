"use strict";
const TOKEN = new URLSearchParams(location.search).get("token") || "";
const TERMINAL_POLL_MS = 1000;

const REASON_TEXT = {
  ready: "可以开始生成",
  configured_unverified: "已配置，首次生成时验证",
  not_configured: "尚未配置任何渠道",
  degraded: "部分渠道不可用",
  invalid: "配置无效，请检查渠道参数",
  provider_verification_not_run: "已配置，首次生成时验证",
  provider_verification_passed: "已验证可用",
  provider_verification_failed: "验证失败",
  provider_verification_stale: "验证已过期，下次生成时重新验证",
  credential_store_available: "凭据可用",
  credential_missing: "凭据缺失",
  credential_environment_missing: "环境变量未设置",
  provider_preferred: "已设为当前渠道（固定模式）",
  provider_auto_selection_enabled: "已恢复自动选择",
  provider_preference_updated: "已更新启用状态",
  provider_removed: "已删除渠道",
  provider_not_found: "渠道不存在或已被删除",
  provider_priority_reordered: "已调整自动选择优先级",
  provider_priority_updated: "已更新权重（自动模式按权重从小到大选择）",
  provider_priority_invalid: "权重须为 1-1000 的整数",
  credential_secret_missing: "请输入密钥后再保存",
  credential_input_channel_unavailable: "请选择当前可用的凭据方式",
  credential_overwrite_confirmation_required: "更换密钥未确认，请重试",
  terminal_entry_unavailable: "当前无法使用终端录入（服务无交互终端）",
  terminal_session_timeout: "终端录入超时，未保存任何配置",
  terminal_session_cancelled: "已取消终端录入；迟到的终端输入将被丢弃，未保存任何配置",
  credential_input_cancelled_or_eof: "终端录入已取消，未保存任何配置",
  unknown_provider: "未知渠道",
  forbidden: "没有权限：请从 leo-ppt config ui 输出的链接进入",
  host_forbidden: "拒绝访问",
  request_body_too_large: "请求内容过大",
  request_body_invalid_json: "请求格式错误",
  config_write_conflict: "配置已被其他操作修改，请刷新后重试",
  "provider_profile_invalid:endpoint_origin": "端点无效：需为 HTTPS origin（不含路径/查询/凭据）",
  "provider_profile_invalid:model": "模型名无效",
  provider_profile_invalid: "渠道配置无效，请检查参数",
  provider_selection_invalid: "当前配置无法完成自动选择，请检查渠道状态",
  provider_selection_required: "暂无可自动选择的渠道：请先在下方配置任一渠道",
};
function reasonText(code) {
  if (code && Object.prototype.hasOwnProperty.call(REASON_TEXT, code)) return REASON_TEXT[code];
  return code ? String(code) : "未知状态";
}

const BUILTIN_LABELS = {
  "openai": "OpenAI 官方",
  "openai-compatible": "自定义中转站（OpenAI 兼容）",
  "atlascloud": "AtlasCloud",
};
const BUILTIN_ENV = {
  "openai": "OPENAI_API_KEY",
  "openai-compatible": "OPENAI_API_KEY",
  "atlascloud": "ATLASCLOUD_API_KEY",
};

const state = { overview: null, channels: null };
const $ = (id) => document.getElementById(id);

function el(tag, options) {
  const node = document.createElement(tag);
  const config = options || {};
  if (config.cls) node.className = config.cls;
  if (config.text !== undefined) node.textContent = config.text;
  if (config.attrs) {
    for (const [key, value] of Object.entries(config.attrs)) node.setAttribute(key, value);
  }
  if (config.children) {
    for (const child of config.children) node.appendChild(child);
  }
  return node;
}

class ApiError extends Error {
  constructor(status, reason) { super(reason); this.status = status; this.reason = reason; }
}
async function api(method, path, body) {
  const init = { method, headers: { "Content-Type": "application/json", "X-Leo-UI-Token": TOKEN } };
  if (body !== undefined) init.body = JSON.stringify(body);
  const response = await fetch(path, init);
  let data = {};
  try { data = await response.json(); } catch (_parseError) { data = {}; }
  if (!response.ok) throw new ApiError(response.status, data.reason_code || ("http_" + response.status));
  return data;
}

function displayName(providerId) {
  for (const item of (state.channels ? state.channels.channels : [])) {
    if (item.id === providerId) return item.display_name;
  }
  if (Object.prototype.hasOwnProperty.call(BUILTIN_LABELS, providerId)) return BUILTIN_LABELS[providerId];
  return providerId;
}
function channelDef(providerId) {
  if (!state.channels) return null;
  return state.channels.channels.find((item) => item.id === providerId) || null;
}

function toast(message, kind) {
  const item = el("div", { cls: "toast-item" + (kind ? " " + kind : ""), text: message });
  $("toast").appendChild(item);
  setTimeout(() => item.remove(), 3600);
}

function withPending(button, action) {
  if (button.disabled) return;
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "处理中…";
  Promise.resolve()
    .then(action)
    .catch((error) => {
      toast(reasonText(error && error.reason), "err");
      // CAS 冲突意味着本地视图已过期：自动刷新以呈现真实配置。
      if (error && error.reason === "config_write_conflict") load();
    })
    .finally(() => { button.disabled = false; button.textContent = label; });
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("已复制到剪贴板", "ok");
  } catch (_clipboardError) {
    toast("复制失败，请手动选择复制", "err");
  }
}

/* ------------------------------------------------------------- 渲染 */
function verificationOf(providerId) {
  const report = state.overview && state.overview.report;
  const entry = report && Array.isArray(report.providers)
    ? report.providers.find((item) => item.provider === providerId) : null;
  // 后端契约：ProviderReport.to_dict() 把验证状态序列化为嵌套 verification.status。
  return entry && entry.verification && entry.verification.status
    ? entry.verification.status : null;
}

function badge(text, kind) { return el("span", { cls: "tag" + (kind ? " " + kind : ""), text }); }

function renderStatus() {
  const overview = state.overview || {};
  const report = overview.report || {};
  const selection = overview.selection;
  const dot = $("status-dot");
  dot.className = "dot " + ({ ready: "", degraded: "warn", invalid: "err" }[report.status] || "idle");
  $("status-text").textContent = reasonText(report.status);
  const mode = overview.mode === "fixed" ? "固定模式" : "自动模式";
  let current = "未选择";
  if (selection) {
    const entry = (overview.providers || []).find((item) => item.provider === selection.provider);
    current = displayName(selection.provider) + (entry && entry.model ? " · " + entry.model : "");
  }
  const detail = $("status-detail");
  detail.textContent = "";
  detail.appendChild(document.createTextNode("选择方式：" + mode + " · 当前渠道："));
  detail.appendChild(el("b", { text: current }));
  if (report.reason_code) {
    detail.appendChild(document.createTextNode(" · " + reasonText(report.reason_code)));
  }
  $("mode-fixed").classList.toggle("active", overview.mode === "fixed");
  $("mode-auto").classList.toggle("active", overview.mode !== "fixed");
  $("configured-hint").textContent = overview.mode === "fixed"
    ? "固定模式：新任务固定使用当前渠道（权重不参与选择）"
    : "自动模式：按权重从小到大自动选择（权重可编辑，或 ↑↓ 调整）";
}

function renderConfigured() {
  const list = $("configured-list");
  list.textContent = "";
  const providers = (state.overview && state.overview.providers ? state.overview.providers : []).filter((item) => item.configured);
  if (!providers.length) {
    list.appendChild(el("div", { cls: "empty", text: "暂无已配置渠道——从下方「添加渠道」开始，两分钟内即可开始生成。" }));
    return;
  }
  const enabledProviders = providers.filter((item) => item.enabled !== false);
  providers.forEach((provider) => {
    // 排序序号以"启用渠道"列表为准（服务端 reorder 为启用全集重排）；
    // 停用渠道不参与排序，按钮禁用，避免与全量列表索引错位。
    const enabledIndex = provider.enabled === false ? -1
      : enabledProviders.findIndex((item) => item.provider === provider.provider);
    const main = el("div", { cls: "chan-main" });
    const title = el("div", { cls: "chan-title", text: displayName(provider.provider) + (provider.model ? " · " + provider.model : "") });
    main.appendChild(title);
    const meta = el("div", { cls: "meta" });
    if (provider.selected) meta.appendChild(el("span", { cls: "tag current", text: "● 当前使用" }));
    if (!provider.credential_available) {
      meta.appendChild(badge(provider.reason_code === "credential_environment_missing" ? "环境变量未设置" : "凭据缺失", "warn"));
    } else {
      meta.appendChild(badge("凭据可用", "ok"));
    }
    const verification = verificationOf(provider.provider);
    if (verification) meta.appendChild(badge(reasonText("provider_verification_" + verification), verification === "passed" ? "ok" : (verification === "failed" ? "err" : "")));
    if (provider.priority !== null && provider.priority !== undefined) meta.appendChild(badge("权重 " + provider.priority));
    main.appendChild(meta);

    const actions = el("div", { cls: "actions" });
    const switchLabel = el("label", { cls: "switch" });
    const enabled = el("input", { attrs: { type: "checkbox", role: "switch", "aria-label": displayName(provider.provider) + " 启用状态" } });
    enabled.checked = provider.enabled !== false;
    enabled.addEventListener("change", () => {
      withPending(enabled, () => api("POST", "/api/provider/enabled", { provider: provider.provider, value: enabled.checked })
        .then((data) => { toast(reasonText(data.reason_code), "ok"); return load(); }));
    });
    switchLabel.appendChild(enabled);
    switchLabel.appendChild(el("span", { text: "启用" }));
    actions.appendChild(switchLabel);

    if (!provider.selected) {
      const preferBtn = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "设为当前" });
      preferBtn.addEventListener("click", () => withPending(preferBtn, () =>
        api("POST", "/api/prefer", { provider: provider.provider })
          .then((data) => { toast(reasonText(data.reason_code), "ok"); return load(); })));
      actions.appendChild(preferBtn);
    }
    if (state.overview.mode !== "fixed") {
      const canSort = enabledIndex >= 0;
      const up = el("button", { cls: "btn alt small", attrs: { type: "button", "aria-label": "上移优先级", disabled: !canSort || enabledIndex === 0 ? "disabled" : null }, text: "↑" });
      const down = el("button", { cls: "btn alt small", attrs: { type: "button", "aria-label": "下移优先级", disabled: !canSort || enabledIndex === enabledProviders.length - 1 ? "disabled" : null }, text: "↓" });
      up.addEventListener("click", () => withPending(up, () => reorder(enabledIndex, enabledIndex - 1)));
      down.addEventListener("click", () => withPending(down, () => reorder(enabledIndex, enabledIndex + 1)));
      actions.appendChild(up); actions.appendChild(down);
      if (canSort) {
        // 权重直接配置（自动模式）：小值优先，值域 1-1000。
        const weightWrap = el("div", { cls: "switch" });
        weightWrap.appendChild(el("span", { text: "权重" }));
        const weightInput = el("input", {
          attrs: {
            type: "number", min: "1", max: "1000", step: "1",
            value: provider.priority == null ? "" : String(provider.priority),
            "aria-label": displayName(provider.provider) + " 权重（1-1000，小值优先）",
          },
        });
        const weightBtn = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "设" });
        weightBtn.addEventListener("click", () => withPending(weightBtn, () => {
          const value = Number.parseInt(weightInput.value, 10);
          if (!Number.isFinite(value)) { toast(reasonText("provider_priority_invalid"), "err"); return Promise.resolve(); }
          return api("POST", "/api/provider/priority", { provider: provider.provider, priority: value })
            .then((data) => { toast(reasonText(data.reason_code), "ok"); return load(); });
        }));
        weightWrap.appendChild(weightInput);
        weightWrap.appendChild(weightBtn);
        actions.appendChild(weightWrap);
      }
    }
    const editBtn = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "修改" });
    editBtn.addEventListener("click", () => openWizard(provider.provider, true));
    const removeBtn = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "删除" });
    removeBtn.addEventListener("click", () => openConfirmRemove(provider.provider));
    actions.appendChild(editBtn); actions.appendChild(removeBtn);

    const row = el("div", { cls: provider.selected ? "chan current" : "chan", children: [main, actions] });
    list.appendChild(row);
  });
}

async function reorder(from, to) {
  const providers = state.overview.providers.filter((item) => item.configured && item.enabled !== false).map((item) => item.provider);
  if (to < 0 || to >= providers.length) return;
  const ordered = providers.slice();
  const moved = ordered.splice(from, 1)[0];
  ordered.splice(to, 0, moved);
  const data = await api("POST", "/api/provider/reorder", { providers: ordered });
  toast(reasonText(data.reason_code), "ok");
  await load();
}

function renderAdd() {
  const grid = $("add-list");
  grid.textContent = "";
  // 添加区展示 CLI 支持的全量渠道（目录 + 内置），与 CLI 选择菜单一一对应；
  // 已配置的不再隐藏——标记「已配置」并提供"重新配置"（可沿用现有密钥），
  // 否则用户无从换密钥，也会误以为渠道从目录消失。
  const configured = new Set(
    (state.overview && state.overview.providers ? state.overview.providers : [])
      .filter((item) => item.configured)
      .map((item) => item.provider)
  );
  let rendered = 0;
  const addCard = (build) => { grid.appendChild(build()); rendered += 1; };
  const configuredBadge = () => badge("已配置 ✓", "ok");
  const cardState = (card, isConfigured) => {
    if (isConfigured) card.classList.add("card-configured");
    return card;
  };
  const actionButton = (providerId, isConfigured) => {
    const btn = el("button", { cls: isConfigured ? "btn alt" : "btn", attrs: { type: "button" }, text: isConfigured ? "重新配置" : "配置" });
    btn.addEventListener("click", () => openWizard(providerId, isConfigured));
    return btn;
  };

  (state.channels ? state.channels.channels : []).forEach((channel) => {
    const isConfigured = configured.has(channel.id);
    addCard(() => {
      const card = cardState(el("div", { cls: "card" }), isConfigured);
      const title = el("div", { cls: "card-title" });
      title.appendChild(el("span", { text: channel.display_name }));
      if (channel.featured) title.appendChild(badge("推荐", "ok"));
      if (isConfigured) title.appendChild(configuredBadge());
      card.appendChild(title);
      const models = el("div", { cls: "models" });
      channel.models.slice(0, 4).forEach((model) => models.appendChild(badge(model)));
      card.appendChild(models);
      const link = el("a", { cls: "link", attrs: { href: channel.key_page, target: "_blank", rel: "noopener noreferrer" }, text: "获取密钥 ↗" });
      card.appendChild(link);
      if (channel.notes) card.appendChild(el("p", { cls: "notes", text: channel.notes.length > 84 ? channel.notes.slice(0, 84) + "…" : channel.notes }));
      card.appendChild(actionButton(channel.id, isConfigured));
      return card;
    });
  });

  Object.keys(BUILTIN_LABELS).forEach((providerId) => {
    const isConfigured = configured.has(providerId);
    addCard(() => {
      const card = cardState(el("div", { cls: "card" }), isConfigured);
      const title = el("div", { cls: "card-title", children: [el("span", { text: BUILTIN_LABELS[providerId] })] });
      if (isConfigured) title.appendChild(configuredBadge());
      card.appendChild(title);
      const isCompatible = providerId === "openai-compatible";
      card.appendChild(el("p", { cls: "notes", text: isCompatible
        ? "任意 OpenAI 兼容中转站：需填写 Base URL（HTTPS origin）与模型，凭据环境变量 OPENAI_API_KEY。"
        : "官方/托管渠道：端点固定，凭据环境变量 " + BUILTIN_ENV[providerId] + "。" }));
      card.appendChild(actionButton(providerId, isConfigured));
      return card;
    });
  });

  if (!rendered) grid.appendChild(el("div", { cls: "empty", text: "渠道目录为空。如需新增目录渠道，参见 references/provider-catalog.md 的贡献流程。" }));
}

async function load() {
  try {
    const [overview, channels] = await Promise.all([api("GET", "/api/overview"), api("GET", "/api/channels")]);
    state.overview = overview; state.channels = channels;
    renderStatus(); renderConfigured(); renderAdd();
  } catch (error) {
    $("status-text").textContent = "加载失败";
    $("status-detail").textContent = reasonText(error && error.reason);
  }
}

/* ------------------------------------------------------------- 向导 */
const wizard = { provider: null, editing: false, step: 1, terminal: { session: null, timer: null } };

function profileOf(providerId) {
  const entry = (state.overview && state.overview.providers ? state.overview.providers : []).find((item) => item.provider === providerId);
  return entry || null;
}

function openWizard(providerId, editing) {
  wizard.provider = providerId;
  wizard.editing = Boolean(editing);
  wizard.step = 1;
  stopTerminalPoll();
  const def = channelDef(providerId);
  const profile = profileOf(providerId);
  $("wizard-sub").textContent = (editing ? "修改渠道：" : "配置渠道：") + displayName(providerId);

  const datalist = $("wiz-models");
  datalist.textContent = "";
  (def ? def.models : []).forEach((model) => datalist.appendChild(el("option", { attrs: { value: model } })));
  $("wiz-model").value = (profile && profile.model) || (def ? def.default_model : "");

  const endpointInput = $("wiz-endpoint");
  const isCompatible = providerId === "openai-compatible";
  endpointInput.value = (profile && profile.endpoint_origin) || (def ? def.endpoint_origin : "") || "";
  endpointInput.disabled = !isCompatible && Boolean(def);
  $("wiz-endpoint-label").textContent = isCompatible ? "Base URL（必填，HTTPS origin）" : "端点（默认已预填）";
  $("wiz-endpoint-hint").textContent = isCompatible
    ? "仅 origin（如 https://api.example.com），不含路径、查询或凭据。"
    : "目录渠道使用注册端点；如需覆盖，须为 HTTPS origin。";

  $("wiz-step1").hidden = false;
  $("wiz-step2").hidden = true;
  $("wiz-wait").hidden = true;
  $("wiz-back").hidden = true;
  $("wiz-next").hidden = false;
  $("wiz-save").hidden = true;
  const dialog = $("config-wizard");
  if (!dialog.open) dialog.showModal();
  $("wiz-model").focus();
}

function buildCredentialOptions() {
  const providerId = wizard.provider;
  const options = $("cred-options");
  options.textContent = "";
  const def = channelDef(providerId);
  const environment = (def && def.credential_environment) || BUILTIN_ENV[providerId] || "";
  const profile = profileOf(providerId);
  const hasCredential = profile && (profile.credential_available || wizard.editing);
  const terminalAvailable = Boolean(state.overview && state.overview.capabilities && state.overview.capabilities.terminal_entry);

  const modes = [];
  modes.push({ mode: "web", title: "网页直接录入", recommended: true });
  if (terminalAvailable) modes.push({ mode: "terminal", title: "终端安全录入", recommended: false });
  modes.push({ mode: "env", title: "环境变量引用", recommended: false });
  if (hasCredential) modes.push({ mode: "keep", title: "保留现有凭据", recommended: false });

  const defaultMode = wizard.editing && hasCredential ? "keep" : "web";
  modes.forEach((entry) => {
    const input = el("input", { attrs: { type: "radio", name: "cred-mode", value: entry.mode } });
    input.checked = entry.mode === defaultMode;
    const head = el("div", { cls: "head" });
    head.appendChild(input);
    head.appendChild(el("b", { text: entry.title }));
    if (entry.recommended) head.appendChild(badge("推荐", "ok"));
    const option = el("label", { cls: "cred-option", children: [head] });
    const detail = el("div", { cls: "cred-detail" });

    if (entry.mode === "web") {
      const secretRow = el("div", { cls: "wait-row" });
      const secret = el("input", { attrs: { type: "password", id: "cred-secret", autocomplete: "off", placeholder: "粘贴或输入 API Key", "aria-label": "API 密钥" } });
      const toggle = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "显示" });
      toggle.addEventListener("click", () => {
        const showing = secret.type === "text";
        secret.type = showing ? "password" : "text";
        toggle.textContent = showing ? "显示" : "隐藏";
      });
      secretRow.appendChild(secret); secretRow.appendChild(toggle);
      detail.appendChild(secretRow);
      detail.appendChild(el("p", { text: "密钥仅写入本机系统钥匙串，但浏览器 DevTools 网络面板在会话内可见请求体。密钥不会显示、保存或回传本页。" }));
    } else if (entry.mode === "terminal") {
      detail.appendChild(el("p", { text: "提交后请在启动 leo-ppt config ui 的终端中输入密钥（输入隐藏）；本页会自动感知完成。" }));
    } else if (entry.mode === "env") {
      const exportLine = "export " + environment + "=<你的密钥>";
      const row = el("div", { cls: "cli-card" });
      row.appendChild(el("code", { text: exportLine }));
      const copy = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "复制" });
      copy.addEventListener("click", () => copyText(exportLine));
      row.appendChild(copy);
      detail.appendChild(row);
      detail.appendChild(el("p", { text: "在 shell 配置或当前会话设置该变量后保存；页面不会传输密钥本身。" }));
    } else {
      detail.appendChild(el("p", { text: "沿用当前已保存的凭据引用，仅更新模型/端点等参数。" }));
    }
    option.appendChild(detail);
    input.addEventListener("change", () => {
      options.querySelectorAll(".cred-option").forEach((node) => node.classList.remove("selected"));
      option.classList.add("selected");
      const warn = $("overwrite-warning");
      if (warn) warn.hidden = entry.mode === "keep" || entry.mode === "env";
    });
    if (input.checked) option.classList.add("selected");
    options.appendChild(option);
  });

  if (wizard.editing && hasCredential) {
    const warning = el("div", {
      cls: "hint",
      attrs: { id: "overwrite-warning" },
      text: "选择网页/终端录入并保存将覆盖已保存的密钥。",
    });
    warning.hidden = defaultMode === "keep" || defaultMode === "env";
    options.appendChild(warning);
  }

  const command = "leo-ppt config credential set --provider " + providerId + " --key-stdin";
  $("cli-command").textContent = command;
}

function selectedMode() {
  const checked = document.querySelector('input[name="cred-mode"]:checked');
  return checked ? checked.value : null;
}

function stopTerminalPoll() {
  if (wizard.terminal.timer) { clearInterval(wizard.terminal.timer); wizard.terminal.timer = null; }
  wizard.terminal.session = null;
}

function closeWizard() {
  stopTerminalPoll();
  const secret = $("cred-secret");
  if (secret) secret.value = "";
  $("config-wizard").close();
}

function startTerminalPoll(sessionId) {
  wizard.terminal.session = sessionId;
  $("wiz-step2").hidden = true;
  $("wiz-wait").hidden = false;
  $("wiz-back").hidden = true;
  $("wiz-save").hidden = true;
  $("wiz-next").hidden = true;
  $("wait-provider").textContent = displayName(wizard.provider);
  wizard.terminal.timer = setInterval(async () => {
    try {
      const data = await api("GET", "/api/credential/session/" + encodeURIComponent(sessionId));
      if (data.state === "completed") {
        stopTerminalPoll();
        toast("配置完成：" + displayName(wizard.provider), "ok");
        closeWizard();
        await load();
      } else if (data.state === "error" || data.state === "unknown") {
        stopTerminalPoll();
        toast(reasonText(data.reason_code), "err");
        $("wiz-wait").hidden = true;
        $("wiz-step2").hidden = false;
        $("wiz-back").hidden = false;
        $("wiz-save").hidden = false;
      }
    } catch (_pollError) {
      /* 网络瞬断时保持等待，下次轮询重试 */
    }
  }, TERMINAL_POLL_MS);
}

async function saveWizard() {
  const providerId = wizard.provider;
  const mode = selectedMode();
  if (!mode) { toast("请选择凭据方式", "err"); return; }
  const body = { provider: providerId, credential: { mode } };
  const model = $("wiz-model").value.trim();
  if (model) body.model = model;
  const endpoint = $("wiz-endpoint").value.trim();
  if (endpoint) body.endpoint_origin = endpoint;
  if (mode === "web") {
    const secret = $("cred-secret");
    if (!secret || !secret.value.trim()) { toast(reasonText("credential_secret_missing"), "err"); return; }
    body.credential.secret = secret.value;
  }
  const data = await api("POST", "/api/provider/configure", body);
  if (mode === "terminal") {
    if (data.session && data.session.id) { startTerminalPoll(data.session.id); return; }
    throw new ApiError(0, "terminal_entry_failed");
  }
  const secret = $("cred-secret");
  if (secret) secret.value = "";
  toast("已保存：" + displayName(providerId) + " · " + reasonText(data.reason_code), "ok");
  closeWizard();
  await load();
}

/* ------------------------------------------------------------- 删除 */
let removeTarget = null;
function openConfirmRemove(providerId) {
  removeTarget = providerId;
  $("remove-body").textContent = "将删除渠道「" + displayName(providerId) + "」的配置：";
  $("confirm-remove").showModal();
}

/* ------------------------------------------------------------- 事件绑定 */
$("add-channel").addEventListener("click", () => {
  const providerId = guessFirstAddable();
  if (providerId) {
    openWizard(providerId, false);
  } else {
    toast("目录渠道均已配置；如需新增目录渠道见 references/provider-catalog.md");
  }
});
function guessFirstAddable() {
  const configured = new Set(
    (state.overview && state.overview.providers ? state.overview.providers : [])
      .filter((item) => item.configured)
      .map((item) => item.provider)
  );
  const channel = (state.channels ? state.channels.channels : []).find((item) => !configured.has(item.id));
  return channel ? channel.id : "openai-compatible";
}

$("wiz-next").addEventListener("click", () => {
  const model = $("wiz-model").value.trim();
  if (!model) { toast("请填写图片模型", "err"); $("wiz-model").focus(); return; }
  if (wizard.provider === "openai-compatible" && !$("wiz-endpoint").value.trim()) {
    toast(reasonText("provider_profile_invalid:endpoint_origin"), "err");
    $("wiz-endpoint").focus(); return;
  }
  buildCredentialOptions();
  wizard.step = 2;
  $("wiz-step1").hidden = true;
  $("wiz-step2").hidden = false;
  $("wiz-back").hidden = false;
  $("wiz-next").hidden = true;
  $("wiz-save").hidden = false;
});
$("wiz-back").addEventListener("click", () => {
  wizard.step = 1;
  stopTerminalPoll();
  $("wiz-step1").hidden = false;
  $("wiz-step2").hidden = true;
  $("wiz-wait").hidden = true;
  $("wiz-back").hidden = true;
  $("wiz-next").hidden = false;
  $("wiz-save").hidden = true;
});
$("wiz-save").addEventListener("click", () => withPending($("wiz-save"), saveWizard));
$("wiz-cancel").addEventListener("click", closeWizard);
$("wait-cancel").addEventListener("click", () => withPending($("wait-cancel"), async () => {
  const sessionId = wizard.terminal.session;
  stopTerminalPoll();
  if (sessionId) {
    try { await api("POST", "/api/credential/session/" + encodeURIComponent(sessionId) + "/cancel", {}); }
    catch (_cancelError) { /* 服务端按超时兜底丢弃迟到输入 */ }
  }
  toast(reasonText("terminal_session_cancelled"));
  closeWizard();
}));
$("wizard-form").addEventListener("submit", (event) => event.preventDefault());

$("remove-cancel").addEventListener("click", () => $("confirm-remove").close());
$("remove-confirm").addEventListener("click", () => withPending($("remove-confirm"), async () => {
  const providerId = removeTarget;
  const data = await api("POST", "/api/provider/remove", { provider: providerId });
  $("confirm-remove").close();
  toast(reasonText(data.reason_code), "ok");
  await load();
}));

$("mode-auto").addEventListener("click", () => withPending($("mode-auto"), () =>
  api("POST", "/api/auto", {}).then((data) => { toast(reasonText(data.reason_code), "ok"); return load(); })));
$("mode-fixed").addEventListener("click", () => {
  const selection = state.overview && state.overview.selection;
  if (!selection) { toast("请先在渠道卡片上配置并「设为当前」", "err"); return; }
  withPending($("mode-fixed"), () =>
    api("POST", "/api/prefer", { provider: selection.provider })
      .then((data) => { toast(reasonText(data.reason_code), "ok"); return load(); }));
});
$("copy-cli").addEventListener("click", () => copyText($("cli-command").textContent));

/* ============================================================= 生成任务 */
const runs = {
  list: null,
  detail: null,
  currentRun: null,
  poll: { timer: null, kind: null },
  lastStatus: {},
};

const EVENT_LABELS = {
  "run.created": "创建任务",
  "run.stage_advanced": "进入阶段",
  "run.retry": "重试",
  "run.cancelled": "取消",
  "run.cleanup": "清理",
  "image.prepared": "图片准备完成",
  "image.recorded": "页面图片完成",
  "image.assembled": "图片装配完成",
  "editable.prepared": "可编辑准备完成",
  "editable.dispatched": "页面已派发",
  "editable.reset": "页面重置",
  "editable.recorded": "页面完成",
  "editable.finalized": "可编辑定稿",
  "upgrade.finalized": "升级定稿",
};
const RUN_STATUS_LABELS = {
  created: "已创建",
  in_progress: "进行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};
const PAGE_STATE_ICONS = {
  recorded: "✔",
  active: "⏳",
  failed: "✗",
  timeout: "⏱",
  pending: "…",
  unknown: "·",
};
const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);
// 时间线优化：连续同类页级事件可折叠为一组（阶段/失败/重试不折叠）。
const COMPRESSIBLE_KINDS = new Set(["image.recorded", "editable.recorded"]);
const DATA_LABELS = {
  actor: "操作者", status: "结果", slide_id: "页", page_id: "页",
  subject: "对象", reason_code: "原因", operation_id: "操作",
  artifact_ref: "产物", evidence_refs: "证据", backend: "渠道",
};
function pageNoOf(data) {
  const match = /^(slide|page)_([0-9]+)$/.exec(String(data.slide_id || data.page_id || ""));
  return match ? parseInt(match[2], 10) : null;
}
function eventTime(event) {
  const parsed = Date.parse(event.at);
  return Number.isFinite(parsed) ? parsed : null;
}

function announce(text) {
  const region = $("live-region");
  if (region) region.textContent = text;
}

function fmtClock(iso) {
  const parsed = new Date(iso);
  return isNaN(parsed.getTime()) ? String(iso) : parsed.toLocaleTimeString("zh-CN", { hour12: false });
}
function fmtDur(seconds) {
  const value = Math.round(Number(seconds));
  if (!Number.isFinite(value) || value < 0) return "";
  if (value < 60) return value + " 秒";
  if (value < 3600) return Math.floor(value / 60) + " 分 " + (value % 60) + " 秒";
  return Math.floor(value / 3600) + " 时 " + Math.round((value % 3600) / 60) + " 分";
}
const ROUTE_LABELS = {
  generate: "图片版",
  "direct-editable": "可编辑版",
  "upgrade-full": "升级（全量）",
  "upgrade-selected": "升级（选定页）",
};
function shortPath(full) {
  if (typeof full !== "string" || !full) return "";
  const parts = full.split("/");
  return parts.slice(-2).join("/");
}

function stopRunsPolling() {
  if (runs.poll.timer) { clearInterval(runs.poll.timer); runs.poll.timer = null; }
  runs.poll.kind = null;
}

function scheduleRunsPolling(kind, fn, interval) {
  stopRunsPolling();
  runs.poll.kind = kind;
  runs.poll.timer = setInterval(() => {
    if (document.hidden) return; // FR8：不可见时暂停
    fn();
  }, interval);
}

async function loadRunsList() {
  try {
    const data = await api("GET", "/api/runs");
    runs.list = data;
    renderRunsList();
  } catch (error) {
    // B5：错误态保留面板头与主动重试入口，不裸奔等 15s 自愈。
    const box = $("runs-list");
    box.textContent = "";
    const panel = el("div", { cls: "panel" });
    const head = el("div", { cls: "section-head", style: "margin:0 0 6px" });
    head.appendChild(el("h2", { text: "生成任务" }));
    const retry = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "重试" });
    retry.addEventListener("click", () => withPending(retry, loadRunsList));
    head.appendChild(retry);
    panel.appendChild(head);
    panel.appendChild(el("div", { cls: "empty", text: "任务列表加载失败：" + reasonText(error && error.reason) }));
    box.appendChild(panel);
  }
}

async function loadRunDetail(runId, opts) {
  const options = opts || {};
  try {
    const query = options.eventsBefore ? "?events_before=" + options.eventsBefore : "";
    const data = await api("GET", "/api/runs/" + encodeURIComponent(runId) + query);
    if (options.prependEvents && runs.detail) {
      data.events_window.events = data.events_window.events.concat(runs.detail.events_window.events);
    }
    const previous = runs.detail;
    runs.detail = data;
    runs.currentRun = runId;
    renderRunDetail();
    if (previous && previous.status !== data.status && TERMINAL_STATUSES.has(data.status)) {
      const label = data.status === "completed" ? "✔ 生成完成" : "✗ 生成失败";
      document.title = label + " · " + data.project + " · Leo PPT";
      announce(label + "：" + data.project);
    }
  } catch (error) {
    if (error && error.reason === "run_not_found") {
      location.hash = "#tab=runs";
      return;
    }
    toast(reasonText(error && error.reason), "err");
  }
}

function timeAgo(minutes) {
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return Math.round(minutes) + " 分钟前";
  return Math.round(minutes / 60) + " 小时前";
}

function renderRunsList() {
  const box = $("runs-list");
  $("run-detail").textContent = "";
  const data = runs.list || { runs: [], home_missing: true };
  // 验收发现 A-1：15s 轮询数据未变时跳过重建，避免点击瞬间节点被替换
  // （与详情页签名跳过同型）。
  const signature = JSON.stringify([
    data.home_missing,
    runs.filter,
    data.runs.map((item) => item.run_id + ":" + item.status + ":" + item.stage + ":" + item.updated_at + ":" + item.stale_minutes).join(","),
  ]);
  if (signature === runs.lastListSig && box.childNodes.length) return;
  runs.lastListSig = signature;
  box.textContent = "";
  runs.filter = runs.filter || "all";
  const panel = el("div", { cls: "panel" });
  const head = el("div", { cls: "section-head", style: "margin:0 0 6px" });
  head.appendChild(el("h2", { text: "生成任务" }));
  const refresh = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "刷新" });
  refresh.addEventListener("click", () => withPending(refresh, loadRunsList));
  head.appendChild(refresh);
  panel.appendChild(head);

  if (!data.runs.length) {
    panel.appendChild(el("div", {
      cls: "empty",
      text: data.home_missing
        ? "未找到任务目录：请设置 LEO_PPT_HOME 或先在宿主会话中发起一次生成（leo-ppt run create）。"
        : "暂无生成任务。在宿主会话发起一次生成（如 leo-ppt run create）后，这里会实时展示进展、预览与过程。",
    }));
    box.appendChild(panel);
    return;
  }
  // B2：状态筛选 chips（纯客户端，含计数）。
  const counts = { all: data.runs.length };
  data.runs.forEach((item) => { counts[item.status] = (counts[item.status] || 0) + 1; });
  const chips = el("div", { cls: "filter-chips", attrs: { role: "group", "aria-label": "任务状态筛选" } });
  [["all", "全部"], ["in_progress", "进行中"], ["failed", "失败"], ["completed", "已完成"]].forEach(([key, label]) => {
    if (key !== "all" && !counts[key]) return;
    const chip = el("button", {
      cls: runs.filter === key ? "active" : "",
      attrs: { type: "button", "aria-pressed": runs.filter === key ? "true" : "false" },
      text: label + " " + (counts[key] || 0),
    });
    chip.addEventListener("click", () => { runs.filter = key; renderRunsList(); });
    chips.appendChild(chip);
  });
  panel.appendChild(chips);
  const visible = runs.filter === "all" ? data.runs : data.runs.filter((item) => item.status === runs.filter);
  if (!visible.length) {
    panel.appendChild(el("div", { cls: "empty", text: "该状态下暂无任务。" }));
    box.appendChild(panel);
    return;
  }
  visible.forEach((item) => {
    const main = el("div", { cls: "run-main" });
    const title = el("div", { cls: "run-title" });
    title.appendChild(document.createTextNode("#" + item.short_id + " " + item.project + " "));
    const statusTag = el("span", { cls: "tag" + (item.status === "failed" ? " err" : (item.status === "completed" ? " ok" : "")) });
    statusTag.textContent = RUN_STATUS_LABELS[item.status] || item.status;
    title.appendChild(statusTag);
    const stale = item.stale_minutes != null && item.stale_minutes >= 5;
    // A3：死进程不得"看起来还活着"——陈旧即停呼吸并明示。
    if (item.status === "in_progress" && !stale) statusTag.classList.add("breath");
    main.appendChild(title);
    const meta = el("div", { cls: "run-meta" });
    const progress = item.progress;
    const total = progress && progress.total_units || 0;
    const completed = progress && progress.completed || 0;
    const failed = progress && progress.failed || 0;
    const progressText = total
      ? "页 " + completed + "/" + total + (failed ? "（" + failed + " 失败）" : "")
      : "";
    const parts = [ROUTE_LABELS[item.route] || item.route, item.stage_label, progressText, timeAgo(Math.max(0, (Date.now() / 1000 - item.updated_at) / 60))];
    if (stale) parts.push("⚠ " + Math.round(item.stale_minutes) + " 分钟无更新");
    meta.textContent = parts.filter(Boolean).join(" · ");
    main.appendChild(meta);
    // B1：页进度条（真实分母 total_units；阶段级仍不显示百分比）。
    if (total) {
      const bar = el("div", { cls: "pgbar", attrs: { role: "progressbar", "aria-label": "页进度 " + completed + "/" + total, "aria-valuemin": "0", "aria-valuemax": String(total), "aria-valuenow": String(completed) } });
      if (completed) bar.appendChild(el("span", { cls: "done", attrs: { style: "width:" + Math.round(completed * 100 / total) + "%" } }));
      if (failed) bar.appendChild(el("span", { cls: "fail", attrs: { style: "width:" + Math.round(failed * 100 / total) + "%" } }));
      main.appendChild(bar);
    }
    const row = el("button", {
      cls: "run-row",
      attrs: {
        type: "button",
        "aria-label": "任务 #" + item.short_id + " " + item.project + "，" + (RUN_STATUS_LABELS[item.status] || item.status) + "，" + progressText,
      },
      children: [main],
    });
    row.addEventListener("click", () => { location.hash = "run=" + item.run_id; });
    panel.appendChild(row);
  });
  box.appendChild(panel);
}

function renderRunDetail() {
  const box = $("run-detail");
  $("runs-list").textContent = "";
  const detail = runs.detail;
  if (!detail) return;
  // E-R1#2：数据签名未变则跳过重建（3s 轮询 × no-store 缩略图会 otherwise
  // 每轮全量重取图片并冲掉过滤/加载更早/焦点状态）。
  const signature = JSON.stringify([
    detail.updated_at, detail.status, detail.stage,
    detail.pages.map((page) => page.number + ":" + page.state + ":" + (page.failure_reason || "")).join(","),
    detail.events_window.events.length,
    detail.events_window.events[0] ? detail.events_window.events[0].seq : null,
  ]);
  if (signature === runs.lastRenderSig && box.childNodes.length) return;
  runs.lastRenderSig = signature;
  box.textContent = "";

  const back = el("button", { cls: "back-link", attrs: { type: "button" }, text: "← 返回任务列表" });
  back.addEventListener("click", () => { location.hash = "tab=runs"; });
  box.appendChild(back);

  const panel = el("div", { cls: "panel", attrs: { style: "margin-top:10px" } });
  const head = el("div", { cls: "run-title", attrs: { style: "font-size:17px" } });
  head.appendChild(document.createTextNode("#" + detail.short_id + " " + detail.project + " · " + (RUN_STATUS_LABELS[detail.status] || detail.status)));
  const refresh = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "刷新" });
  refresh.addEventListener("click", () => withPending(refresh, () => loadRunDetail(runs.currentRun)));
  const headRow = el("div", { cls: "wait-row", children: [head, refresh] });
  panel.appendChild(headRow);
  panel.appendChild(el("div", { cls: "run-meta", text: [ROUTE_LABELS[detail.route] || detail.route, detail.created_at ? "开始于 " + fmtClock(detail.created_at) : null, detail.duration_seconds != null ? "总耗时 " + fmtDur(detail.duration_seconds) : null].filter(Boolean).join(" · ") }));

  if (detail.stale_minutes != null && detail.stale_minutes >= 5) {
    panel.appendChild(el("div", { cls: "stale-note", text: "数据已 " + Math.round(detail.stale_minutes) + " 分钟未更新，进程可能已退出（本页仅观察落盘状态）。" }));
  }

  // 流程条（FR3）
  const flow = el("div", { cls: "flow", attrs: { role: "list", "aria-label": "生成流程" } });
  detail.steps.forEach((step, index) => {
    if (index > 0) flow.appendChild(el("span", { cls: "flow-arrow", text: "→" }));
    const cls = "flow-step " + (step.state === "done" ? "done" : step.state === "current" ? (detail.status === "failed" ? "fail" : "current") : "");
    const node = el("span", { cls, attrs: { role: "listitem" } });
    const mark = step.state === "done" ? "✔ " : step.state === "current" ? "⏳ " : "";
    node.appendChild(document.createTextNode(mark + step.label + (step.duration_seconds != null ? " " + Math.round(step.duration_seconds) + "s" : "")));
    flow.appendChild(node);
  });
  // 交付卡（FR5）——B3：终态 run 交付上移到流程条后（验收用户第一屏即见）；
  // 函数定义须先于 flow 追加（const TDZ），非终态在链路表后兜底调用。
  let deliveryAppended = false;
  const appendDelivery = () => {
    if (deliveryAppended) return;
    deliveryAppended = true;
    const delivery = detail.delivery || {};
    if (delivery.deck_path || delivery.gates || delivery.failure_summary) {
      panel.appendChild(el("h2", { attrs: { style: "font-size:16px;margin:18px 0 4px" }, text: "交付" }));
      if (delivery.deck_path) {
        const row = el("div", { cls: "cli-card" });
        row.appendChild(el("code", { text: "…/" + shortPath(delivery.deck_path), attrs: { title: delivery.deck_path } }));
        const copy = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "复制完整路径" });
        copy.addEventListener("click", () => copyText(delivery.deck_path));
        row.appendChild(copy);
        panel.appendChild(row);
      }
      if (delivery.gates) {
        const gates = el("div", { cls: "run-meta" });
        delivery.gates.forEach((gate) => {
          gates.appendChild(el("span", { cls: "tag" + (gate.status === "passed" ? " ok" : " err"), text: gate.name + (gate.status === "passed" ? " ✔" : " ✗") }));
        });
        panel.appendChild(gates);
      }
      if (delivery.failure_summary) {
        const failure = delivery.failure_summary;
        panel.appendChild(el("div", { cls: "stale-note", text: "失败摘要：" + [failure.failed_stage ? "失败于 " + failure.failed_stage : null, failure.failures != null ? failure.failures + " 项失败" : null, failure.recovery_action ? "恢复建议：" + failure.recovery_action : null].filter(Boolean).join("；") || "详见时间线失败事件。" }));
      }
    }
  };
  panel.appendChild(flow);
  if (TERMINAL_STATUSES.has(detail.status)) appendDelivery();

  // 页网格（FR4/FR12）
  const progress = detail.progress;
  if (progress && progress.total_units) {
    panel.appendChild(el("div", { cls: "run-meta", text: "页进度 " + (progress.completed || 0) + "/" + progress.total_units + (progress.failed ? "（" + progress.failed + " 失败）" : "") }));
  }
  const grid = el("div", { cls: "page-grid", attrs: { role: "list", "aria-label": "页面状态网格" } });
  detail.pages.forEach((page) => {
    const state = page.state || "unknown";
    const cell = el("button", { cls: "page-cell st-" + state, attrs: { type: "button", role: "listitem", "aria-label": "第 " + page.number + " 页，" + state + (page.failure_reason ? "，" + reasonText(page.failure_reason) : "") + (page.backend ? "，渠道 " + page.backend : "") } });
    cell.appendChild(el("span", { cls: "pg-no", text: "#" + page.number }));
    if (state === "recorded" && detail.route === "generate") {
      const img = el("img", { attrs: { src: "/api/runs/" + encodeURIComponent(detail.run_id) + "/pages/" + page.number + ".png", alt: "" , loading: "lazy" } });
      cell.appendChild(img);
    } else {
      cell.appendChild(el("span", { cls: "pg-ico", text: PAGE_STATE_ICONS[state] || "·" }));
    }
    cell.addEventListener("click", () => {
      if (state === "recorded" && detail.route === "generate") openLightbox(detail, page.number);
      else focusPageEvents(page.number, detail.route); // FR5 分流
    });
    grid.appendChild(cell);
  });
  panel.appendChild(grid);

  // 时间线（FR6/FR14）
  panel.appendChild(el("h2", { attrs: { style: "font-size:16px;margin:18px 0 4px" }, text: "过程时间线" }));
  const windowMeta = detail.events_window;
  const timeline = el("div", { cls: "timeline" });
  if (windowMeta.bad_lines) {
    timeline.appendChild(el("div", { cls: "run-meta", text: windowMeta.bad_lines + " 行事件无法解析（已跳过）" }));
  }
  const events = windowMeta.events || [];
  if (!events.length) {
    timeline.appendChild(el("div", { cls: "empty", text: "暂无事件数据。" }));
  }
  // 时间线优化：最新在前；连续同类页级事件折叠为组；显示相邻间隔耗时
  // （≥60s 标 warn——"卡在哪"一眼可见）；详情按字段中文标签可读化。
  const reversed = events.slice().reverse();
  const rows = [];
  for (let index = 0; index < reversed.length; index += 1) {
    const event = reversed[index];
    const data = event.data && typeof event.data === "object" ? event.data : {};
    const previous = reversed[index + 1];
    const compressiblePair =
      COMPRESSIBLE_KINDS.has(event.kind) && pageNoOf(data) !== null && previous &&
      previous.kind === event.kind && pageNoOf(previous.data || {}) !== null;
    if (compressiblePair && rows.length && rows[rows.length - 1].type === "group" && rows[rows.length - 1].kind === event.kind) {
      rows[rows.length - 1].events.push(event);
    } else if (compressiblePair) {
      rows.push({ type: "group", kind: event.kind, events: [event, previous] });
      index += 1; // previous 已被组吸收，跳过
    } else {
      rows.push({ type: "single", event: event });
    }
  }
  // 行间间隔：本行最新时刻距上一行结束（该行最旧事件）过了多久。
  const rowTopAt = (row) => (row.type === "single" ? eventTime(row.event) : eventTime(row.events[0]));
  const rowBottomAt = (row) => (row.type === "single" ? eventTime(row.event) : eventTime(row.events[row.events.length - 1]));
  rows.forEach((row, index) => {
    if (!index) { row.gapSeconds = null; return; }
    const aboveBottom = rowBottomAt(rows[index - 1]);
    const top = rowTopAt(row);
    row.gapSeconds = aboveBottom !== null && top !== null ? Math.max(0, Math.round((aboveBottom - top) / 1000)) : null;
  });
  rows.forEach((row) => {
    if (row.type === "single") {
      timeline.appendChild(buildTimelineItem(row.event, row.gapSeconds));
    } else {
      timeline.appendChild(buildTimelineGroup(row));
    }
  });
  if (windowMeta.events.length >= 200) {
    const earlier = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "加载更早事件" });
    earlier.addEventListener("click", () => withPending(earlier, () => loadRunDetail(runs.currentRun, { eventsBefore: windowMeta.events[0].seq, prependEvents: true })));
    timeline.appendChild(earlier);
  }
  panel.appendChild(timeline);

  // 链路（FR7）
  panel.appendChild(el("h2", { attrs: { style: "font-size:16px;margin:18px 0 4px" }, text: "链路与渠道" }));
  const providers = detail.backend_stats && detail.backend_stats.providers ? detail.backend_stats.providers : {};
  const providerNames = Object.keys(providers);
  if (!providerNames.length) {
    panel.appendChild(el("div", { cls: "empty", text: "仅图片路线记录渠道调用统计；本任务暂无数据。" }));
  } else {
    const table = el("table", { cls: "trace-table" });
    const header = el("tr");
    ["渠道", "调用", "尝试", "tokens"].forEach((label) => header.appendChild(el("th", { text: label })));
    table.appendChild(header);
    providerNames.forEach((name) => {
      const row = el("tr");
      [name, providers[name].calls, providers[name].attempts, detail.backend_stats.tokens_recorded ? providers[name].tokens : "未记录"].forEach((value) => row.appendChild(el("td", { text: String(value) })));
      table.appendChild(row);
    });
    panel.appendChild(table);
  }

  if (!deliveryAppended) appendDelivery();
  box.appendChild(panel);

  // B4：轮询重渲染后重放时间线过滤（签名未变时不会走到这里）。
  if (runs.filterPage) {
    focusPageEvents(runs.filterPage.page, runs.filterPage.route, { replay: true, silent: true });
  }

  // 轮询策略（FR8）：进行中 3s；终态停（保留手动刷新）
  stopRunsPolling();
  if (!TERMINAL_STATUSES.has(detail.status)) {
    scheduleRunsPolling("detail", () => loadRunDetail(runs.currentRun), 3000);
  }
}

function focusPageEvents(pageNumber, route, opts) {
  const options = opts || {};
  if (!options.replay) runs.filterPage = { page: pageNumber, route: route };
  // E-R1#3：按路线选择单元形状（image=slide_NN / editable=page_NNN，双候选），
  // 全等或数字边界匹配（避免 slide_01 误配 slide_011）。
  const padded = String(pageNumber);
  const candidates = route === "generate"
    ? ["slide_" + padded.padStart(2, "0")]
    : ["page_" + padded.padStart(3, "0"), "slide_" + padded.padStart(2, "0")];
  const pattern = new RegExp("^(" + candidates.join("|") + ")(?![0-9])");
  const items = Array.from(document.querySelectorAll(".tl-item"));
  let matched = items.filter((item) => pattern.test(item.getAttribute("data-page") || ""));
  // 验收发现 A-3：image 路线失败页没有页级事件（失败痕迹是全局 run.retry），
  // 无匹配时回落定位最近的失败事件，避免"点失败页扑空"。
  if (!matched.length) {
    matched = items.filter((item) => item.classList.contains("tl-fail"));
  }
  items.forEach((item) => { item.style.display = matched.length ? "none" : ""; });
  matched.forEach((item) => {
    item.style.display = "";
    if (item.classList.contains("tl-group")) {
      const body = item.querySelector(".tl-body");
      const toggle = item.querySelector(".tl-toggle");
      if (body && body.hidden) { body.hidden = false; if (toggle) { toggle.textContent = toggle.textContent.replace("展开", "收起"); toggle.setAttribute("aria-expanded", "true"); } }
    }
  });
  // B4：过滤提示条（可见子集 + 退出按钮），重渲染后由重放恢复。
  const existing = $("filter-note");
  if (existing) existing.remove();
  const timeline = document.querySelector(".timeline");
  if (timeline && matched.length) {
    const note = el("div", { cls: "stale-note", attrs: { id: "filter-note" } });
    note.appendChild(document.createTextNode("已过滤：第 " + pageNumber + " 页相关事件（" + matched.length + " 条）"));
    const showAll = el("button", { cls: "btn alt small", attrs: { type: "button" }, text: "显示全部" });
    showAll.addEventListener("click", () => {
      runs.filterPage = null;
      document.querySelectorAll(".tl-item").forEach((item) => { item.style.display = ""; });
      const removed = $("filter-note");
      if (removed) removed.remove();
    });
    note.appendChild(showAll);
    timeline.insertBefore(note, timeline.firstChild);
  }
  const first = matched[0];
  if (first && !options.replay) {
    first.scrollIntoView({ block: "center" });
    first.setAttribute("tabindex", "-1");
    first.focus({ preventScroll: true });
  }
  if (!options.silent) announce("已过滤为第 " + pageNumber + " 页事件，共 " + matched.length + " 条");
}

function buildTimelineItem(event, gapSeconds) {
  const data = event.data && typeof event.data === "object" ? event.data : {};
  const failed = event.kind === "run.retry" || String(data.status || "").indexOf("fail") >= 0 || String(data.status || "") === "error";
  const staged = event.kind === "run.stage_advanced" || event.kind === "run.created";
  const item = el("div", { cls: "tl-item" + (failed ? " tl-fail" : staged ? " tl-stage" : " tl-ok") });
  const headRow = el("div", { cls: "tl-head" });
  headRow.appendChild(el("span", { cls: "tl-time", text: fmtClock(event.at) }));
  if (gapSeconds !== null && gapSeconds > 0) {
    headRow.appendChild(el("span", { cls: "tl-gap" + (gapSeconds >= 60 ? " slow" : ""), text: "+" + fmtDur(gapSeconds) }));
  }
  const subject = data.subject || data.slide_id || data.page_id || "";
  const subjectText = pageNoOf(data) !== null ? "第 " + pageNoOf(data) + " 页" : (subject ? subject : "");
  headRow.appendChild(document.createTextNode(
    (EVENT_LABELS[event.kind] || event.kind) +
    (subjectText ? " · " + subjectText : "") +
    (data.reason_code ? " · " + reasonText(data.reason_code) : "")
  ));
  const body = el("div", { cls: "tl-body", attrs: { hidden: failed ? null : "hidden" } });
  body.appendChild(buildReadableEventData(data));
  const toggle = el("button", { cls: "tl-toggle", attrs: { type: "button", "aria-expanded": failed ? "true" : "false" }, text: failed ? "收起" : "详情" });
  toggle.addEventListener("click", () => {
    const showing = body.hidden;
    body.hidden = !showing;
    toggle.textContent = showing ? "收起" : "详情";
    toggle.setAttribute("aria-expanded", showing ? "true" : "false");
  });
  headRow.appendChild(toggle);
  item.appendChild(headRow);
  item.appendChild(body);
  item.setAttribute("data-page", subject ? String(subject) : "");
  return item;
}

function buildTimelineGroup(row) {
  // 连续同类页级事件折叠："页面图片完成 7 页（#1 #2 #4…）"。
  const numbers = row.events.map((event) => pageNoOf(event.data || {}));
  const subjects = row.events.map((event) => String((event.data || {}).slide_id || (event.data || {}).page_id || "")).filter(Boolean);
  const group = el("div", { cls: "tl-item tl-group" });
  group.setAttribute("data-page", subjects.join(" "));
  const headRow = el("div", { cls: "tl-head" });
  // events 按新→旧排列（与时间线方向一致）：组头显示最新时刻、距上一行的间隔与组内跨度。
  const latest = row.events[0];
  const earliest = row.events[row.events.length - 1];
  const spanSeconds =
    eventTime(latest) !== null && eventTime(earliest) !== null
      ? Math.max(0, Math.round((eventTime(latest) - eventTime(earliest)) / 1000))
      : null;
  headRow.appendChild(el("span", { cls: "tl-time", text: fmtClock(latest.at) }));
  if (row.gapSeconds !== null && row.gapSeconds > 0) {
    headRow.appendChild(el("span", { cls: "tl-gap" + (row.gapSeconds >= 60 ? " slow" : ""), text: "+" + fmtDur(row.gapSeconds) }));
  }
  if (spanSeconds !== null && spanSeconds > 0) {
    // 跨度是中性信息（组内持续时长），保持灰；仅行间间隔 ≥60s 才用警示橙。
    headRow.appendChild(el("span", { cls: "tl-gap", text: "跨度 " + fmtDur(spanSeconds) }));
  }
  headRow.appendChild(document.createTextNode(
    (EVENT_LABELS[row.kind] || row.kind) + " · " + row.events.length + " 页（#" + numbers.filter(Boolean).join(" #") + "）"
  ));
  const body = el("div", { cls: "tl-body", attrs: { hidden: "hidden" } });
  row.events.forEach((event) => {
    const data = event.data && typeof event.data === "object" ? event.data : {};
    body.appendChild(el("div", {
      cls: "tl-sub",
      text: fmtClock(event.at) + " · 第 " + pageNoOf(data) + " 页" + (data.backend ? " · " + data.backend : ""),
    }));
  });
  const toggle = el("button", { cls: "tl-toggle", attrs: { type: "button", "aria-expanded": "false" }, text: "展开 " + row.events.length + " 条" });
  toggle.addEventListener("click", () => {
    const showing = body.hidden;
    body.hidden = !showing;
    toggle.textContent = showing ? "收起" : "展开 " + row.events.length + " 条";
    toggle.setAttribute("aria-expanded", showing ? "true" : "false");
  });
  headRow.appendChild(toggle);
  group.appendChild(headRow);
  group.appendChild(body);
  return group;
}

function buildReadableEventData(data) {
  const wrap = el("div", {});
  Object.entries(data).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") return;
    const line = el("div", { cls: "tl-kv" });
    line.appendChild(el("span", { cls: "tl-k", text: (DATA_LABELS[key] || key) }));
    let text = typeof value === "object" ? JSON.stringify(value) : String(value);
    if (key === "reason_code") text = reasonText(value);
    line.appendChild(el("span", { cls: "tl-v", text: text }));
    wrap.appendChild(line);
  });
  const raw = el("details", { cls: "tl-raw" });
  raw.appendChild(el("summary", { text: "原始 JSON" }));
  raw.appendChild(el("pre", { attrs: { style: "margin:4px 0;white-space:pre-wrap;word-break:break-all" }, text: JSON.stringify(data, null, 1) }));
  wrap.appendChild(raw);
  return wrap;
}

let lightboxState = null;
function openLightbox(detail, pageNumber) {
  const recorded = detail.pages.filter((page) => page.state === "recorded");
  const numbers = recorded.map((page) => page.number);
  const index = Math.max(0, numbers.indexOf(pageNumber));
  lightboxState = { numbers, index };
  $("lightbox-img").src = "/api/runs/" + encodeURIComponent(detail.run_id) + "/pages/" + numbers[index] + ".png";
  $("lightbox-img").alt = "第 " + numbers[index] + " 页预览";
  const dialog = $("page-lightbox");
  if (!dialog.open) dialog.showModal();
  $("lightbox-prev").focus();
}
function lightboxStep(delta) {
  if (!lightboxState || !lightboxState.numbers.length) return;
  const next = lightboxState.index + delta;
  if (next < 0 || next >= lightboxState.numbers.length) {
    announce(next < 0 ? "已是第一页" : "已是最后一页");
    return;
  }
  lightboxState.index = next;
  const number = lightboxState.numbers[next];
  $("lightbox-img").src = "/api/runs/" + encodeURIComponent(runs.detail.run_id) + "/pages/" + number + ".png";
  $("lightbox-img").alt = "第 " + number + " 页预览";
}
$("lightbox-prev").addEventListener("click", () => lightboxStep(-1));
$("lightbox-next").addEventListener("click", () => lightboxStep(1));
$("lightbox-close").addEventListener("click", () => $("page-lightbox").close());
$("page-lightbox").addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft") lightboxStep(-1);
  if (event.key === "ArrowRight") lightboxStep(1);
});

/* ------------------------------------------------------------- Tab 路由 */
function parseHash() {
  const hash = (location.hash || "").replace(/^#/, "");
  const match = hash.match(/^run=([0-9a-f]{8,64})$/);
  if (match) return { tab: "runs", run: match[1] };
  if (hash === "tab=runs") return { tab: "runs", run: null };
  return { tab: "channels", run: null };
}

function applyRoute(route) {
  stopRunsPolling();
  const isRuns = route.tab === "runs";
  $("tab-channels").setAttribute("aria-selected", isRuns ? "false" : "true");
  $("tab-runs").setAttribute("aria-selected", isRuns ? "true" : "false");
  $("channels-view").hidden = isRuns;
  $("runs-view").hidden = !isRuns;
  document.title = isRuns ? "生成任务 · Leo PPT 控制台" : "Leo PPT · 图片渠道管理";
  if (isRuns) {
    if (route.run) {
      loadRunDetail(route.run);
    } else {
      runs.detail = null;
      runs.currentRun = null;
      loadRunsList();
      scheduleRunsPolling("list", loadRunsList, 15000);
    }
  }
}

$("tab-channels").addEventListener("click", () => { location.hash = ""; });
$("tab-runs").addEventListener("click", () => { location.hash = "tab=runs"; });
window.addEventListener("hashchange", () => applyRoute(parseHash()));
document.addEventListener("visibilitychange", () => {
  // FR8：恢复可见立即拉取一次，避免停摆期间的终态延迟。
  if (!document.hidden) {
    const route = parseHash();
    if (route.tab === "runs") {
      if (route.run) loadRunDetail(route.run);
      else loadRunsList();
    }
  }
});

/* ------------------------------------------------------------- 启动 */
function boot() {
  if (window.__LEO_INITIAL__ && window.__LEO_INITIAL__.overview) {
    state.overview = window.__LEO_INITIAL__.overview;
    state.channels = window.__LEO_INITIAL__.channels;
    renderStatus(); renderConfigured(); renderAdd();
    load();
  } else {
    load();
  }
  if (window.__LEO_INITIAL__ && window.__LEO_INITIAL__.runs) {
    runs.list = window.__LEO_INITIAL__.runs;
  }
  applyRoute(parseHash());
}
boot();
