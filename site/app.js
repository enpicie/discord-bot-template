import { applyName, buildZip, combinationKey, validateName, validatePublicKey } from "./generator.js";

const $ = (id) => document.getElementById(id);
const bundles = new Map(); // combination key -> Promise<{path: text}>

let manifest;
let currentFiles = {};
let selectedPath = "README.md";

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of children) node.append(child);
  return node;
}

function enabledFeatures() {
  return new Set(manifest.features.map((f) => f.key).filter((key) => $(`feature-${key}`).checked));
}

function loadBundle(key) {
  if (!bundles.has(key)) {
    bundles.set(key, fetch(`bundles/${key}.json`).then((r) => {
      if (!r.ok) throw new Error(`bundle ${key}: HTTP ${r.status}`);
      return r.json();
    }));
  }
  return bundles.get(key);
}

function nameOrPlaceholder() {
  const name = $("name").value.trim();
  return name && !validateName(name, manifest) ? name : null;
}

// ── Preview ──────────────────────────────────────────────────────────────────

function renderTree(files) {
  const tree = $("tree");
  tree.replaceChildren();
  let lastDir = null;
  for (const path of Object.keys(files).sort()) {
    const slash = path.lastIndexOf("/");
    const dir = slash === -1 ? "" : path.slice(0, slash);
    const depth = dir ? dir.split("/").length : 0;
    if (dir !== lastDir && dir) {
      tree.append(el("li", { className: "dir", textContent: `${dir}/`, style: `padding-left:${8 + (depth - 1) * 12}px` }));
    }
    lastDir = dir;
    const button = el("button", { type: "button", textContent: path.slice(slash + 1) });
    button.style.paddingLeft = `${8 + depth * 12}px`;
    button.dataset.path = path;
    button.addEventListener("click", () => showFile(path));
    tree.append(el("li", {}, button));
  }
}

function showFile(path) {
  if (!(path in currentFiles)) path = "README.md";
  selectedPath = path;
  $("viewer-path").textContent = path;
  $("viewer").firstElementChild.textContent = currentFiles[path];
  for (const button of $("tree").querySelectorAll("button")) {
    button.setAttribute("aria-current", String(button.dataset.path === path));
  }
}

async function refreshPreview() {
  const enabled = enabledFeatures();
  const key = combinationKey(enabled);
  try {
    const files = await loadBundle(key);
    if (key !== combinationKey(enabledFeatures())) return; // superseded by a newer change
    const name = nameOrPlaceholder() ?? manifest.placeholder_name;
    currentFiles = applyName(files, name, manifest, $("key-dev").value.trim(), $("key-prod").value.trim());
    const labels = manifest.features.filter((f) => enabled.has(f.key)).map((f) => f.label);
    $("summary").textContent =
      `${Object.keys(currentFiles).length} files · ${labels.length ? labels.join(", ") : "base only"}` +
      (nameOrPlaceholder() ? "" : ` · shown with the placeholder name "${manifest.placeholder_name}"`);
    renderTree(currentFiles);
    showFile(selectedPath);
  } catch (e) {
    $("summary").textContent = `Couldn't load the preview: ${e.message}`;
  }
  renderSteps();
}

// ── Next steps ───────────────────────────────────────────────────────────────

function codeBlock(command) {
  const pre = el("pre", {}, el("code", { textContent: command }));
  const copy = el("button", { type: "button", className: "copy", textContent: "Copy" });
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(command);
      copy.textContent = "Copied";
    } catch {
      copy.textContent = "Select & copy";
    }
    setTimeout(() => (copy.textContent = "Copy"), 1500);
  });
  return [copy, pre];
}

function step(text, ...commands) {
  const li = el("li", {}, text);
  for (const command of commands) li.append(...codeBlock(command));
  return li;
}

function renderSteps() {
  const name = nameOrPlaceholder() ?? "<bot-name>";
  const keysSet = $("key-dev").value.trim() && $("key-prod").value.trim();
  $("steps").replaceChildren(
    step("Unzip it and go into the folder.", `unzip ${name}.zip && cd ${name}`),
    step("Make the first commit.", `git init -b main && git add -A && git commit -m "Initialize ${name}"`),
    step("Create the GitHub repo and push.", `gh repo create enpicie/${name} --private --source . --push`),
    step(
      "Create a dev app and a prod app in the Discord Developer Portal (discord.com/developers/applications)." +
        (keysSet ? "" : " Put each app's Public Key in config.env (DISCORD_PUBLIC_KEY_DEV / _PROD) and commit."),
    ),
    step(
      "Set the repo variables and secrets. Each secret prompts for the bot token (Bot tab → Reset Token).",
      "gh variable set DISCORD_APP_ID_DEV --body <dev application id>",
      "gh variable set DISCORD_APP_ID_PROD --body <prod application id>",
      "gh secret set DISCORD_BOT_TOKEN_DEV",
      "gh secret set DISCORD_BOT_TOKEN_PROD",
    ),
    step("Deploy dev — any branch other than main deploys dev.", "git checkout -b dev && git push -u origin dev"),
    step(
      "Copy interactions_endpoint_url from the deploy job's log into the dev app's General Information → " +
        "Interactions Endpoint URL. Discord pings it to verify when you save.",
    ),
    step(
      "Register the slash commands: in the Actions tab, run Dev Pipeline with \"Run Discord command registration\" " +
        "checked. Invite the bot (OAuth2 → URL Generator → scopes bot + applications.commands) and try /ping.",
    ),
    step(
      "Go to prod: push a version tag. The Release Pipeline deploys prod and registers every command automatically; " +
        "point the prod app's Interactions Endpoint URL at the prod output.",
      "git tag 1.0.0 && git push origin 1.0.0",
    ),
  );
}

// ── Form ─────────────────────────────────────────────────────────────────────

function showError(id, message) {
  $(`${id}-error`).textContent = message ?? "";
  $(id).setAttribute("aria-invalid", String(Boolean(message)));
}

function validateForm() {
  const name = $("name").value.trim();
  const nameError = name ? validateName(name, manifest) : "Enter a bot name.";
  const devError = validatePublicKey($("key-dev").value.trim(), manifest);
  const prodError = validatePublicKey($("key-prod").value.trim(), manifest);
  showError("name", nameError);
  showError("key-dev", devError);
  showError("key-prod", prodError);
  return !(nameError || devError || prodError);
}

async function download(event) {
  event.preventDefault();
  if (!validateForm()) return;
  const name = $("name").value.trim();
  const files = applyName(
    await loadBundle(combinationKey(enabledFeatures())),
    name, manifest, $("key-dev").value.trim(), $("key-prod").value.trim(),
  );
  const blob = new Blob([buildZip(files, name)], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const link = el("a", { href: url, download: `${name}.zip` });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $("status").textContent = `Downloaded ${name}.zip (${Object.keys(files).length} files). Next steps are below.`;
  $("next-steps").scrollIntoView({ behavior: "smooth" });
}

async function init() {
  manifest = await (await fetch("manifest.json")).json();
  $("name").maxLength = manifest.max_name_len;

  for (const feature of manifest.features) {
    const id = `feature-${feature.key}`;
    $("features").append(el("div", { className: "feature" },
      el("input", { type: "checkbox", id, checked: true }),
      el("label", { htmlFor: id, textContent: feature.label }),
      el("p", { className: "help", textContent: feature.description }),
    ));
    $(id).addEventListener("change", refreshPreview);
  }

  $("name").addEventListener("input", () => {
    if ($("name-error").textContent) validateForm();
    refreshPreview();
  });
  for (const id of ["key-dev", "key-prod"]) $(id).addEventListener("input", refreshPreview);
  $("generator").addEventListener("submit", download);

  await refreshPreview();
}

init().catch((e) => {
  $("summary").textContent = `Couldn't load the generator: ${e.message}`;
});
