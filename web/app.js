const SID = "web-" + Math.random().toString(36).slice(2, 10);
const chat = document.getElementById("chat");
const input = document.getElementById("q");
const sendBtn = document.getElementById("send");

if (input) input.addEventListener("keydown", e => { if (e.key === "Enter") ask(); });
if (sendBtn) sendBtn.addEventListener("click", ask);

function addDiv(cls, text) {
  const d = document.createElement("div");
  d.className = cls;
  d.textContent = text;
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
  return d;
}

function addCitations(box, citations) {
  if (!citations || !citations.length) return;
  const seen = new Set(
    [...box.querySelectorAll("a")].map(a => a.dataset.key).filter(Boolean)
  );
  for (const c of citations) {
    const key = c.doc_id || `${c.subject}|${c.source_url}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const a = document.createElement("a");
    a.href = c.source_url || "#";
    a.target = "_blank";
    a.rel = "noopener";
    a.dataset.key = key;
    a.textContent = `[${c.subject || "来源"}] `;
    box.appendChild(a);
  }
}

async function ask(question) {
  const q = (question || input.value).trim();
  if (!q) return;
  input.value = "";
  addDiv("q", "你: " + q);
  const citeBox = addDiv("cite", "");
  const ansBox = addDiv("a", "助手: ");
  const status = addDiv("status", "正在检索…");

  if (sendBtn) sendBtn.disabled = true;

  try {
    const resp = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SID, question: q }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "", event = "";
    let gotToken = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) {
            const data = JSON.parse(line.slice(5));
            if (event === "token") {
              if (!gotToken) {
                status.remove();
                gotToken = true;
              }
              ansBox.textContent += data.text;
            } else if (event === "citation") {
              addCitations(citeBox, [data]);
            } else if (event === "done") {
              status.remove();
              if (data.cached) ansBox.textContent += "  (缓存)";
              if (data.citations) {
                citeBox.textContent = "";
                addCitations(citeBox, data.citations);
              }
            } else if (event === "error") {
              status.remove();
              ansBox.textContent += `\n[错误] ${data.message || "请求失败"}`;
            }
          }
          chat.scrollTop = chat.scrollHeight;
        }
      }
    }
  } catch (err) {
    status.remove();
    ansBox.textContent += `\n[错误] ${err.message || "请求失败，请重试"}`;
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    chat.scrollTop = chat.scrollHeight;
  }
}

function clearSession() { location.reload(); }
