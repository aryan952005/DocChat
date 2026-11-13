# DocChat UI requirements (design brief for Google Stitch)

Use this to generate the design. Then hand the result to Claude Code to build in React.

## 1. What the product is
DocChat answers questions ONLY from documents the user uploads (PDF, Markdown, text) and always shows
where the answer came from (file name and page). If the answer is not in the docs, it says so.
Users: engineers searching internal developer docs. One shared workspace, no login.

## 2. Screens (design all of these)
1. Chat with answers (main screen, desktop 1280 wide)
2. No chat open (empty state)
3. Message states: direct reply, answer with sources, not found, loading, error
4. Mobile chat (390 wide), sidebar opens from a menu button
5. Optional: upload in progress and upload error

## 3. Layout
- Left sidebar (about 280 px), right chat area.
- Sidebar, top to bottom:
  - App name/logo
  - LIBRARY: card listing every uploaded document, one row each (icon, file name, "PDF . 6 pages . 9 chunks").
    The list scrolls when long. A "N documents" count. An "Add a document" button below it.
    Helper text: ".pdf, .md or .txt, up to 10 MB"
  - CONVERSATIONS: "New chat" button FIRST, directly above the history. Then every past chat, one per row
    (title + date), newest first, the open chat highlighted, list scrolls.
- Chat area: header with chat title, scrolling messages, input bar fixed at the bottom.
- Mobile: sidebar hidden, a menu button in the top bar opens it. Chat fills the screen.

## 4. Components and exact content

### Message: user
Right-aligned bubble with the question text.

### Message: assistant (docs answer)
- Answer text. Plain text with line breaks and bullet lists. No markdown rendering, no images.
- SOURCES row: one chip per source, text "payments-api-sample-v2.pdf, page 3".
- A small status BADGE. Exactly three badge texts exist:
  - "Direct reply" (neutral): greetings and chat about the conversation. No sources.
  - "Searched docs . N retries" (positive): N is 0, 1 or 2. Shown with sources.
  - "Not found" (warning): no sources. Answer text is always:
    "I couldn't find this in the uploaded documentation. Try rephrasing or upload the relevant doc."

### Loading
Assistant-style bubble: animated dots and the text "Thinking..." (replies can take 5 to 30 seconds).

### Errors (shown as an assistant-style message, visibly different colour)
- "Something went wrong. Try again."
- "AI service is unavailable."

### Input bar
Text input (placeholder "Ask about your docs...") and a Send button. Disabled while loading
and when no chat is open (placeholder "Start a new chat to ask a question").

### Upload states
Button label changes to "Uploading..." and is disabled. Success: the new row appears in the Library.
Error: short message under the button, for example "File is larger than 10 MB" or "Only .pdf, .md and .txt files are allowed".

## 5. Behaviour the design must support
- Clicking "New chat" opens an empty chat and adds it to the top of the history.
- Clicking a past chat loads its saved messages.
- The user's message appears at once, then "Thinking...", then the answer replaces it.
- Everything reloads from the server on refresh.

## 6. Out of scope (do NOT design)
Login/profile, settings, dark/light toggle (pick one theme), delete or rename chat, delete document,
document preview, streaming text, markdown or code-block rendering, agent trace panel, share buttons, notifications.

## 7. Style direction (your choice, I like these)
- Not generic "AI app": no purple/blue gradients, no glowing orbs, no emoji, no robot icons.
- Three directions already drawn (reference screenshots from the Claude design canvas):
  - A "Paper and Ink": cream background, forest green, terracotta accent, serif headings, answer card with dashed
    "sources" footer, tilted stamp-style badge.
  - B "Terminal Night": near-black green, lime and amber, monospace, no bubbles (`you >` / `docchat >` lines),
    sources like `[1] file.pdf:p3`.
  - C "Citrus Slate": cream, sunny yellow sidebar, coral, thick black outlines with hard shadows.
- Text contrast at least 4.5:1. Buttons and rows at least 44 px tall. Visible keyboard focus.

## 8. Data each element shows (from the backend, so the design uses real fields)
- Document: filename, chunks (page count is optional, may be dropped)
- Chat: title (default "New chat"), createdAt
- Message: role (user or assistant), content, sources [{filename, page}], route ("docs" or "direct"), retries (0 to 2)

## 9. Short prompts to paste into Stitch (one per screen)

Main screen:
"Desktop web app called DocChat, a chat that answers questions only from uploaded documents. Left sidebar 280px:
logo, a Library card listing uploaded documents (icon, file name, 'PDF . 6 pages . 9 chunks'), a dashed 'Add a document'
button, then Conversations with a 'New chat' button on top and a scrollable list of past chats (title and date), one per row.
Right side: chat header, user bubbles on the right, assistant answers on the left with a Sources row of chips
('payments-api-sample-v2.pdf, page 3') and a small status badge 'Searched docs . 0 retries'. Input bar at the bottom with Send.
Style: [pick A, B or C above]. No gradients, no emoji."

Empty state:
"Same layout, no chat open: centered prompt 'Ask anything about your docs', short helper text, a New chat button, disabled input bar."

Message states:
"A sheet showing assistant message variants: direct reply (neutral badge 'Direct reply'), docs answer with sources and badge
'Searched docs . 1 retry', not found (warning badge 'Not found'), loading ('Thinking...' with animated dots), and two error messages."

Mobile:
"Mobile 390px version of the chat: top bar with menu button, chat title and New chat; messages; input bar. The sidebar opens from the menu."

## 10. What to hand over to Claude Code
1. Screenshots of every screen (desktop and mobile).
2. The exported code (HTML/CSS) or a Figma link if Stitch gives one.
3. The colours (hex), fonts and corner radius you finally chose, written as a short list.
4. Any screen you changed after generating, marked clearly.
Claude Code will turn it into React components: UploadPanel, SessionList, ChatWindow, MessageBubble, SourceList (see CLAUDE.md folder structure).

## 11. FINAL DESIGN DECISIONS (these override sections 3 and 7 above)
Chosen design: "Paper and Ink", Layout 1 (three columns). Source: Claude design canvas, board "Layout 1: Three columns".

- Layout: left sidebar 260 px (logo, conversations, New chat pinned at the bottom), centre chat, right Library panel 300 px.
- Library panel hides and shows: a pill in the chat header (book icon, "Library", on/off switch) and a small arrow inside the panel.
  Open by default. When hidden, the chat uses the full width.
- Conversations: one row per chat (title, and a date derived from createdAt: Today, Yesterday, or "Nov 11"); the open chat is highlighted; list scrolls.
- Library: card row per document (icon, file name, "PDF . 9 chunks", "Added Nov 13"), then a dashed "Add a document" button with the allowed types and the 10 MB limit.
  Page count is NOT in the API, so it is not shown. Show type, chunks and the date from uploadedAt.
- Logo: geometric letter D with a tail and three text lines (forest green, one pale terracotta line). Wordmark "DocChat" in Libre Baskerville Bold.
- Fonts: Libre Baskerville (logo, titles, first line of an answer), Source Sans 3 (all other text). No italics except "Thinking...".
- Colours: paper #FBF7EF, panel #EFE7D6 and #F5EFE1, lines #D9CDB4, ink #1E2A26, muted #5C5648, forest #23483C, terracotta #B4472A, answer card #FFFEFA.
- Messages: user bubble forest green with cream text; assistant card with a thin border, a Sources row and a stamp-style badge
  (terracotta outline, small capitals) with the three badge texts from section 4.
- Not designed in the canvas, so derive them from this style: empty state, not-found and direct-reply messages, error messages, upload states, mobile.
  Mobile: the sidebar and Library become slide-in panels opened from the top bar.
