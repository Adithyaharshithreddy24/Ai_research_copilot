import { useEffect, useMemo, useState } from "react";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

async function parseResponse(response) {
  const text = await response.text();
  let data = {};

  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    const detail = data?.detail || "Request failed";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  return data;
}

async function loginUser(payload) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseResponse(response);
}

async function sendMessage({ userId, chatId, mode, message, files }) {
  const formData = new FormData();
  formData.append("user_id", userId);
  formData.append("message", message);
  formData.append("mode", mode || "keyword");
  if (chatId) formData.append("chat_id", chatId);

  for (const file of files) {
    formData.append("files", file);
  }

  const response = await fetch(`${API_BASE_URL}/chat/message`, {
    method: "POST",
    body: formData
  });
  return parseResponse(response);
}

async function runLiterature(chatId) {
  const response = await fetch(`${API_BASE_URL}/actions/literature`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId })
  });
  return parseResponse(response);
}

async function runResearchGaps(chatId) {
  const response = await fetch(`${API_BASE_URL}/actions/research-gap`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId })
  });
  return parseResponse(response);
}

async function runCitation(chatId, style) {
  const response = await fetch(`${API_BASE_URL}/actions/citation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, style })
  });
  return parseResponse(response);
}

function normalizeText(value) {
  return String(value || "")
    .replace(/\r/g, "")
    .trim();
}

function splitIntoReadablePoints(text) {
  const normalized = normalizeText(text);
  if (!normalized) return [];

  const explicitLines = normalized
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  if (explicitLines.length > 1) return explicitLines;

  return normalized
    .split(/(?<=[.!?])\s+(?=[A-Z])/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function parseStructuredSectionsFromText(text) {
  const normalized = normalizeText(text);
  if (!normalized) return [];

  const sectionTitles = [
    "Introduction",
    "Key Themes",
    "Methods",
    "Findings",
    "Trends",
    "Overview",
    "Background",
    "Conclusion"
  ];

  const escapedTitles = sectionTitles
    .map((title) => title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");

  const matcher = new RegExp(`(${escapedTitles})\\s*:`, "gi");
  const matches = [...normalized.matchAll(matcher)];

  if (matches.length === 0) {
    return [{ title: "Overview", points: splitIntoReadablePoints(normalized) }];
  }

  const sections = [];
  for (let i = 0; i < matches.length; i += 1) {
    const current = matches[i];
    const next = matches[i + 1];
    const title = current[1];
    const start = current.index + current[0].length;
    const end = next ? next.index : normalized.length;
    const body = normalized.slice(start, end).trim();
    if (!body) continue;
    sections.push({
      title,
      points: splitIntoReadablePoints(body)
    });
  }

  return sections.length
    ? sections
    : [{ title: "Overview", points: splitIntoReadablePoints(normalized) }];
}

function summarizeToTwentyWords(text) {
  const words = normalizeText(text).split(/\s+/).filter(Boolean);
  if (words.length === 0) return "Summary unavailable for this paper.";
  if (words.length <= 20) return words.join(" ");
  return `${words.slice(0, 20).join(" ")}...`;
}

function formatLiteratureReview(review) {
  if (!review) {
    return [{ title: "Overview", points: ["No literature review returned."] }];
  }

  if (typeof review === "string") {
    const trimmed = review.trim();
    let candidate = trimmed;

    if (candidate.startsWith("```")) {
      const lines = candidate.split("\n");
      if (lines.length >= 3) {
        candidate = lines.slice(1, -1).join("\n").trim();
      }
    }

    try {
      const parsed = JSON.parse(candidate);
      review = parsed;
    } catch {
      return parseStructuredSectionsFromText(trimmed);
    }
  }

  if (Array.isArray(review?.paper_insights) || review?.overview || review?.synthesis) {
    const sections = [];

    if (review?.overview) {
      sections.push({
        title: "Overview",
        points: splitIntoReadablePoints(review.overview)
      });
    }

    if (Array.isArray(review?.paper_insights)) {
      review.paper_insights.forEach((paper, idx) => {
        const points = [
          paper?.focus ? `Focus: ${paper.focus}` : "",
          paper?.method ? `Method: ${paper.method}` : "",
          paper?.finding ? `Finding: ${paper.finding}` : "",
          paper?.limitation ? `Limitation: ${paper.limitation}` : ""
        ].filter(Boolean);

        if (points.length) {
          sections.push({
            title: paper?.title || `Paper ${idx + 1}`,
            points
          });
        }
      });
    }

    if (review?.synthesis) {
      sections.push({
        title: "Synthesis",
        points: splitIntoReadablePoints(review.synthesis)
      });
    }

    if (review?.research_gaps) {
      sections.push({
        title: "Research Gaps",
        points: splitIntoReadablePoints(review.research_gaps)
      });
    }

    if (review?.future_direction) {
      sections.push({
        title: "Future Direction",
        points: splitIntoReadablePoints(review.future_direction)
      });
    }

    if (sections.length) return sections;
  }

  const sections = [
    ["Introduction", review.introduction],
    ["Key Themes", review.key_themes],
    ["Methods", review.methods],
    ["Findings", review.findings],
    ["Trends", review.trends]
  ];

  return sections
    .filter(([, value]) => value)
    .map(([title, value]) => ({
      title,
      points: splitIntoReadablePoints(value)
    }));
}

function formatGapText(text) {
  const normalized = normalizeText(text);
  if (!normalized) return [];

  const labelMap = [
    ["Limitations", /limitations?\s*:/i],
    ["Missing Aspects", /missing aspects?\s*:/i],
    ["Future Work", /future work\s*:/i],
    ["Research Gap", /research gap\s*:/i]
  ];

  const found = labelMap
    .map(([title, pattern]) => {
      const match = normalized.match(pattern);
      return match ? { title, index: match.index, length: match[0].length } : null;
    })
    .filter(Boolean)
    .sort((a, b) => a.index - b.index);

  if (!found.length) return [{ title: "Research Gap", points: splitIntoReadablePoints(normalized) }];

  const sections = found.map((item, index) => {
    const next = found[index + 1];
    const bodyStart = item.index + item.length;
    const bodyEnd = next ? next.index : normalized.length;
    return {
      title: item.title,
      points: splitIntoReadablePoints(normalized.slice(bodyStart, bodyEnd))
    };
  }).filter((section) => section.points.length);

  return sections.length
    ? sections
    : [{ title: "Research Gap", points: splitIntoReadablePoints(normalized) }];
}

function formatMessageText(text) {
  return normalizeText(text)
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function getAuthorLine(authors) {
  if (Array.isArray(authors)) return authors.join(", ");
  return normalizeText(authors);
}

function getPaperLink(paper) {
  const direct = String(paper?.pdf_url || "").trim();
  if (direct) return direct;

  const title = String(paper?.title || "").trim();
  if (!title) return "";

  return `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`;
}

function App() {
  const [stage, setStage] = useState("auth");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [user, setUser] = useState(null);

  const [workspaceMode, setWorkspaceMode] = useState("");
  const [workspaceTab, setWorkspaceTab] = useState("chat");
  const [chatId, setChatId] = useState("");

  const [keyword, setKeyword] = useState("");
  const [keywordGoal, setKeywordGoal] = useState("");
  const [paperPrompt, setPaperPrompt] = useState("");

  const [message, setMessage] = useState("");
  const [files, setFiles] = useState([]);
  const [messages, setMessages] = useState([]);
  const [papers, setPapers] = useState([]);

  const [actionOutput, setActionOutput] = useState({ kind: "literature", sections: [] });
  const [citationStyle, setCitationStyle] = useState("APA");
  const [error, setError] = useState("");

  const [loading, setLoading] = useState({
    login: false,
    startKeyword: false,
    startPaper: false,
    send: false,
    literature: false,
    gaps: false,
    citation: false
  });

  useEffect(() => {
    setName(localStorage.getItem("research_copilot_name") || "");
    setEmail(localStorage.getItem("research_copilot_email") || "");
  }, []);

  const modeTitle = useMemo(() => {
    if (workspaceMode === "keyword") return "Keyword Discovery";
    if (workspaceMode === "paper") return "Paper Discussion";
    return "Workspace";
  }, [workspaceMode]);

  const setBusy = (key, value) => {
    setLoading((prev) => ({ ...prev, [key]: value }));
  };

  function resetWorkspace() {
    setWorkspaceMode("");
    setWorkspaceTab("chat");
    setChatId("");
    setMessage("");
    setFiles([]);
    setMessages([]);
    setPapers([]);
    setActionOutput({ kind: "literature", sections: [] });
  }

  async function handleLogin(e) {
    e.preventDefault();
    setError("");
    setBusy("login", true);
    try {
      const data = await loginUser({ name, email });
      setUser(data);
      localStorage.setItem("research_copilot_name", name);
      localStorage.setItem("research_copilot_email", email);
      resetWorkspace();
      setStage("hub");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("login", false);
    }
  }

  async function startKeywordWorkspace(e) {
    e.preventDefault();
    if (!keyword.trim()) {
      setError("Enter a keyword to begin.");
      return;
    }

    setError("");
    setBusy("startKeyword", true);
    const kickoff = keywordGoal.trim() ? `${keyword.trim()}\nGoal: ${keywordGoal.trim()}` : keyword.trim();

    try {
      const data = await sendMessage({
        userId: user.user_id,
        chatId: "",
        mode: "keyword",
        message: kickoff,
        files: []
      });
      setWorkspaceMode("keyword");
      setWorkspaceTab("chat");
      setChatId(data.chat_id || "");
      setMessages([
        { role: "user", text: kickoff },
        { role: "assistant", text: data.message || "" }
      ]);
      setPapers(Array.isArray(data?.papers) ? data.papers : []);
      setActionOutput({
        kind: "literature",
        sections: [{ title: "Workspace Ready", points: ["Use the Actions tab for literature review, research gaps, and citations."] }]
      });
      setStage("workspace");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("startKeyword", false);
    }
  }

  async function startPaperWorkspace(e) {
    e.preventDefault();
    if (!files.length) {
      setError("Upload at least one PDF.");
      return;
    }

    setError("");
    setBusy("startPaper", true);
    const kickoff =
      paperPrompt.trim() ||
      "Use only my uploaded paper(s) as context. Summarize them and help me discuss methods, findings, and gaps.";

    try {
      const data = await sendMessage({
        userId: user.user_id,
        chatId: "",
        mode: "paper",
        message: kickoff,
        files
      });
      setWorkspaceMode("paper");
      setWorkspaceTab("chat");
      setChatId(data.chat_id || "");
      setMessages([
        { role: "user", text: kickoff },
        { role: "assistant", text: data.message || "" }
      ]);
      setPapers([]);
      setFiles([]);
      setActionOutput({
        kind: "literature",
        sections: [{ title: "Workspace Ready", points: ["Use the Actions tab to generate literature review, gaps, and citations from your uploaded papers."] }]
      });
      setStage("workspace");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("startPaper", false);
    }
  }

  async function handleSendMessage(e) {
    e.preventDefault();
    if (!chatId) {
      setError("Start a workspace first.");
      return;
    }
    if (!message.trim() && files.length === 0) {
      setError("Type a message or attach files.");
      return;
    }

    setError("");
    setBusy("send", true);
    const userMessage = message.trim() || "Please include the attached PDF(s) in context.";
    setMessages((prev) => [...prev, { role: "user", text: userMessage }]);

    try {
      const data = await sendMessage({
        userId: user.user_id,
        chatId,
        mode: workspaceMode || "keyword",
        message: userMessage,
        files
      });
      if (data?.chat_id) setChatId(data.chat_id);
      setPapers(Array.isArray(data?.papers) ? data.papers : papers);
      setMessages((prev) => [...prev, { role: "assistant", text: data.message || "" }]);
      setMessage("");
      setFiles([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("send", false);
    }
  }

  async function handleLiterature() {
    if (!chatId) return;
    setError("");
    setBusy("literature", true);
    try {
      const data = await runLiterature(chatId);
      setActionOutput({ kind: "literature", sections: formatLiteratureReview(data?.literature_review) });
      setWorkspaceTab("actions");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("literature", false);
    }
  }

  async function handleGaps() {
    if (!chatId) return;
    setError("");
    setBusy("gaps", true);
    try {
      const data = await runResearchGaps(chatId);
      setActionOutput({ kind: "gaps", gaps: Array.isArray(data?.gaps) ? data.gaps : [] });
      setWorkspaceTab("actions");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("gaps", false);
    }
  }

  async function handleCitation() {
    if (!chatId) return;
    setError("");
    setBusy("citation", true);
    try {
      const data = await runCitation(chatId, citationStyle);
      const text = typeof data?.citations === "string" ? data.citations : "No citations returned.";
      setActionOutput({
        kind: "literature",
        sections: [{ title: `${citationStyle} Citations`, points: splitIntoReadablePoints(text) }]
      });
      setWorkspaceTab("actions");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("citation", false);
    }
  }

  function goToModeSelection() {
    setError("");
    resetWorkspace();
    setStage("hub");
  }

  function logout() {
    setError("");
    setUser(null);
    resetWorkspace();
    setStage("auth");
  }

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <p className="product-tag">Research Co-Pilot</p>
          <h1>Professional Research Workspace</h1>
          <p className="subtitle">Clear flow. Focused screens. No clutter.</p>
        </div>
        {user && (
          <div className="account-chip">
            <strong>{name || "Researcher"}</strong>
            <span>{email}</span>
          </div>
        )}
      </header>

      {stage === "auth" && (
        <section className="card auth-card">
          <h2>Sign In</h2>
          <form className="form" onSubmit={handleLogin}>
            <label>
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label>
              Email
              <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
            </label>
            <button type="submit" disabled={loading.login}>
              {loading.login ? "Connecting..." : "Enter Workspace"}
            </button>
          </form>
        </section>
      )}

      {stage === "hub" && (
        <section className="hub-grid">
          <article className="card mode-card">
            <h2>Discover by Keyword</h2>
            <p className="muted">Start from a topic and discover relevant papers.</p>
            <form className="form" onSubmit={startKeywordWorkspace}>
              <label>
                Topic
                <input
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="Reinforcement Learning"
                  required
                />
              </label>
              <label>
                Optional focus
                <input
                  value={keywordGoal}
                  onChange={(e) => setKeywordGoal(e.target.value)}
                  placeholder="Applications in robotics"
                />
              </label>
              <button type="submit" disabled={loading.startKeyword}>
                {loading.startKeyword ? "Starting..." : "Start Keyword Mode"}
              </button>
            </form>
          </article>

          <article className="card mode-card">
            <h2>Discuss Uploaded Paper(s)</h2>
            <p className="muted">Upload PDFs and get focused help from chat + actions.</p>
            <form className="form" onSubmit={startPaperWorkspace}>
              <label>
                PDF files
                <input
                  type="file"
                  accept=".pdf"
                  multiple
                  onChange={(e) => setFiles(Array.from(e.target.files || []))}
                />
              </label>
              <label>
                Optional instruction
                <input
                  value={paperPrompt}
                  onChange={(e) => setPaperPrompt(e.target.value)}
                  placeholder="Explain methods and limitations"
                />
              </label>
              <button type="submit" disabled={loading.startPaper}>
                {loading.startPaper ? "Starting..." : "Start Paper Mode"}
              </button>
            </form>
          </article>
        </section>
      )}

      {stage === "workspace" && (
        <section className="workspace-shell">
          <aside className="card sidebar">
            <h3>{modeTitle}</h3>
            <p className="muted mono">Chat: {chatId}</p>
            {workspaceMode === "paper" && (
              <p className="mode-note">
                Paper mode is grounded to uploaded PDF context only.
              </p>
            )}

            <nav className="tab-nav" aria-label="Workspace Sections">
              <button
                type="button"
                className={workspaceTab === "chat" ? "tab active" : "tab"}
                onClick={() => setWorkspaceTab("chat")}
              >
                Chat
              </button>
              <button
                type="button"
                className={workspaceTab === "actions" ? "tab active" : "tab"}
                onClick={() => setWorkspaceTab("actions")}
              >
                Actions
              </button>
              {workspaceMode === "keyword" && (
                <button
                  type="button"
                  className={workspaceTab === "papers" ? "tab active" : "tab"}
                  onClick={() => setWorkspaceTab("papers")}
                >
                  Papers
                </button>
              )}
            </nav>

            <div className="sidebar-actions">
              <button type="button" className="ghost" onClick={goToModeSelection}>
                New Workspace
              </button>
              <button type="button" className="ghost" onClick={logout}>
                Logout
              </button>
            </div>
          </aside>

          <main className="card main-panel">
            {workspaceTab === "chat" && (
              <>
                <h2>Conversation</h2>
                <form className="form" onSubmit={handleSendMessage}>
                  <label>
                    Message
                    <textarea
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      rows={4}
                      placeholder={
                        workspaceMode === "paper"
                          ? "Ask about your uploaded paper only (methods, findings, limitations)."
                          : "Ask for summary, comparison, methods, gaps, or citations."
                      }
                    />
                  </label>
                  <label>
                    Optional: attach additional PDFs
                    <input
                      type="file"
                      accept=".pdf"
                      multiple
                      onChange={(e) => setFiles(Array.from(e.target.files || []))}
                    />
                  </label>
                  <button type="submit" disabled={loading.send}>
                    {loading.send ? "Sending..." : "Send"}
                  </button>
                </form>

                <div className="chat-feed">
                  {messages.length === 0 && <p className="muted">No messages yet.</p>}
                  {messages.map((item, idx) => (
                    <article key={`${item.role}-${idx}`} className={`bubble ${item.role}`}>
                      <h4>{item.role === "user" ? "You" : "Assistant"}</h4>
                      <div className="message-body">
                        {formatMessageText(item.text).map((line, lineIdx) => (
                          <p key={`${item.role}-${idx}-${lineIdx}`}>{line}</p>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              </>
            )}

            {workspaceTab === "actions" && (
              <>
                <h2>Actions & Deliverables</h2>
                <div className="actions-row">
                  <button type="button" onClick={handleLiterature} disabled={loading.literature}>
                    {loading.literature ? "Generating..." : "Literature Review"}
                  </button>
                  <button type="button" onClick={handleGaps} disabled={loading.gaps}>
                    {loading.gaps ? "Analyzing..." : "Research Gaps"}
                  </button>
                </div>
                <div className="citation-block">
                  <select value={citationStyle} onChange={(e) => setCitationStyle(e.target.value)}>
                    <option value="APA">APA</option>
                    <option value="MLA">MLA</option>
                    <option value="IEEE">IEEE</option>
                    <option value="Chicago">Chicago</option>
                  </select>
                  <button type="button" onClick={handleCitation} disabled={loading.citation}>
                    {loading.citation ? "Formatting..." : "Generate Citations"}
                  </button>
                </div>

                {actionOutput.kind === "gaps" ? (
                  <div className="gap-list">
                    {actionOutput.gaps?.length ? (
                      actionOutput.gaps.map((gap, idx) => (
                        <article className="gap-card" key={`${gap?.title || "gap"}-${idx}`}>
                          <h4>{gap?.title || `Paper ${idx + 1}`}</h4>
                          <div className="gap-sections">
                            {formatGapText(gap?.gap || "").map((section, sectionIdx) => (
                              <div className="gap-section" key={`${gap?.title || "gap"}-${sectionIdx}`}>
                                <p className="section-kicker">{section.title}</p>
                                <ul className="point-list">
                                  {section.points.map((point, pointIdx) => (
                                    <li key={`${gap?.title || "gap"}-${sectionIdx}-${pointIdx}`}>{point}</li>
                                  ))}
                                </ul>
                              </div>
                            ))}
                          </div>
                        </article>
                      ))
                    ) : (
                      <p className="muted">No gaps found yet.</p>
                    )}
                  </div>
                ) : actionOutput.sections?.length ? (
                  <div className="review-sections">
                    {actionOutput.sections.map((section, idx) => (
                      <article className="review-card" key={`${section.title}-${idx}`}>
                        <p className="section-kicker">{section.title}</p>
                        <ul className="point-list">
                          {section.points?.map((point, pointIdx) => (
                            <li key={`${section.title}-${idx}-${pointIdx}`}>{point}</li>
                          ))}
                        </ul>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="review-card">
                    <p>Run an action to generate output.</p>
                  </div>
                )}
              </>
            )}

            {workspaceTab === "papers" && workspaceMode === "keyword" && (
              <>
                <h2>Paper Context</h2>
                <div className="paper-grid">
                  {papers.length === 0 && <p className="muted">No papers available in current chat yet.</p>}
                  {papers.map((paper, idx) => (
                    <article className="paper-card" key={`${paper?.title || "paper"}-${idx}`}>
                      <h4>{paper?.title || "Untitled"}</h4>
                      <p className="paper-meta">{getAuthorLine(paper?.authors) || "Authors not listed"}</p>
                      <p className="paper-summary">{summarizeToTwentyWords(paper?.summary)}</p>
                      {getPaperLink(paper) && (
                        <a href={getPaperLink(paper)} target="_blank" rel="noreferrer">
                          Open source
                        </a>
                      )}
                    </article>
                  ))}
                </div>
              </>
            )}
          </main>
        </section>
      )}

      {error && <p className="error-banner">{error}</p>}
    </div>
  );
}

export default App;
