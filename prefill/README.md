# Application Prefill

A small Chrome extension that fills the boring fields on a job application form — name,
email, phone, links, college, notice period — and then gets out of the way.

**It never submits anything.** That is the design, not a limitation. See
[Why it stops short of submitting](#why-it-stops-short-of-submitting).

Takes an application from roughly 20 minutes to 3.

---

## Install (one minute, no store listing)

1. Open `chrome://extensions` in Chrome or Edge.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked** and select this `prefill` folder.
4. The options page opens on first install — fill in your details and **Save profile**.
5. Pin the extension so its button is visible in the toolbar.

To use: open any application form, click the extension button, review what it filled,
answer the questions it left, attach your resume, and submit it yourself.

---

## How it works

Your details are **not** kept in a file in this repository. Nothing personal is committed
here. They live in `chrome.storage.local` under a single key, `profile`, inside your own
browser profile — written once from the options page:

```json
{
  "firstName": "…", "lastName": "…", "fullName": "…",
  "email": "…", "phone": "…", "location": "Bangalore, India",
  "linkedin": "https://linkedin.com/in/…",
  "github": "https://github.com/…",
  "portfolio": "https://….vercel.app",
  "college": "…", "degree": "…", "gradYear": "2026",
  "noticePeriod": "Immediate", "experience": "0",
  "company": "None", "currentCtc": "…", "expectedCtc": "…"
}
```

What happens when you click the toolbar button:

```
click
  ↓
background.js   injects matcher.js + content.js into that one tab
  ↓             (activeTab — one tab, one click, no standing access)
content.js      reads chrome.storage.local → profile
  ↓
matcher.js      for each visible input / textarea / select:
  ↓               1. gather its label — label[for], aria-label,
                     aria-labelledby, wrapping <label>, placeholder,
                     sibling text, name attribute
                  2. test that text against 17 ordered regexes → a key
                  3. look up profile[key]
                  4. fill it, or record why it was skipped
  ↓
content.js      panel: what was filled, what you must answer yourself
```

Filling is not a plain `el.value = x`. React tracks a field's value on the DOM node, so a
direct assignment is silently reverted. The matcher goes through the native `value` setter
and then dispatches `input` and `change`, which is what makes it work on Ashby's
React-rendered forms.

## What it fills

It matches on the **visible label** next to each field, not on the site's internal field
names. That is deliberate — the three major providers are structured completely differently:

| Provider | Structure | Why names don't work |
|---|---|---|
| Lever | Server-rendered, stable names (`name`, `email`, `urls[LinkedIn]`) | Fine, but custom questions are opaque `cards[uuid][field0]` |
| Greenhouse | Often embedded on the company's own domain | The form may not be in the page's own HTML |
| Ashby | Rendered entirely in React | **No name attributes at all** |

Label matching is the only approach that works across all three, and it also handles
company career portals the radar has never seen.

Recognised fields: first/last/full name, email, phone, LinkedIn, GitHub, portfolio,
location, college, degree, graduation year, notice period, years of experience, current
company, current CTC, expected CTC.

## What it refuses to touch

- Captcha fields, CSRF tokens and anything matching `token` or `honeypot`
- Hidden and `display:none` fields — a hidden duplicate is often a bot trap
- File inputs — attach your resume yourself
- Password fields
- Any field that already has a value (it will not overwrite your edits)

After filling, every changed field gets a green outline and a panel lists what was filled,
what was skipped, and **which questions you still need to answer**.

---

## Why it stops short of submitting

Two reasons, and the second is the one that actually matters.

**It would not work.** All three providers gate submission behind bot detection. Checked
directly on their live pages:

| Provider | What is on the apply form |
|---|---|
| Lever | reCAPTCHA and hCaptcha, Cloudflare Bot Management (`__cf_bm` cookie) |
| Ashby | reCAPTCHA, Cloudflare |
| Greenhouse | reCAPTCHA |

Automating past that means defeating captcha and bot detection. It risks the account, and
Cloudflare blocks by IP — so tripping it can lock you out of applying by hand too.

**It would not help.** Every one of these forms has questions only you can answer: why this
company, what you built, your visa status. A bot leaves them blank or pastes something
generic, and a reviewer sees that immediately. Three hundred generic applications perform
worse than twenty considered ones.

So the extension removes the typing and leaves the thinking. The captcha gets solved by a
human because a human is genuinely there.

---

## Privacy

Your profile is stored with `chrome.storage.local` — this browser, this computer. It is
never uploaded, and the extension makes no network requests of any kind.

The manifest requests no host permissions. It uses `activeTab`, which grants access to one
tab, for one click, when you press the button. It is not running in the background on pages
you visit.

**`chrome.storage.local` is not encrypted.** It sits in plaintext on disk in your Chrome
profile folder, so anyone with access to your unlocked computer can read it — exactly like
Chrome's built-in autofill, which stores the same kind of data the same way.

For a name, email, phone and public profile links that is a reasonable trade. Do **not** put
anything genuinely sensitive in these fields, even when a form asks for it: no Aadhaar, PAN,
passport number, date of birth or bank details. Type those by hand each time.

Note also that the profile belongs to the browser profile, not to you — on a shared or
college machine, it stays in that browser after you log out of the website.

---

## Testing a change

`test/mock-forms.html` reproduces all three provider shapes, including Ashby's nameless
React inputs and a hidden honeypot field. Serve the `prefill` folder and open it:

```
python -m http.server 8144
```

Then in the console:

```js
JobPrefill.fill({ fullName: "A Candidate", email: "a@example.com", phone: "9000000000" })
```

It returns `{ filled, skipped, unmatched }`. The current matcher fills 22 of 24 fields
across the three forms, leaving exactly the two open-ended essay questions — and leaves the
captcha, CSRF, file and hidden fields untouched.
