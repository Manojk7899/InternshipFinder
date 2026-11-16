// Usage: node tools/find-board.mjs razorpay swiggy zomato
// Prints which public job boards (if any) each company name resolves to,
// so you can paste the working ones into companies.json.
const names = process.argv.slice(2);
if (!names.length) { console.log('usage: node tools/find-board.mjs <company> [company...]'); process.exit(1); }
const cap = n => n.split('-').map(s => s[0].toUpperCase() + s.slice(1)).join('');
const probe = async (url, pick) => {
  try { const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
    if (!r.ok) return 0; return pick(await r.json()) || 0; } catch { return 0; }
};
for (const n of names) {
  const gh = await probe(`https://boards-api.greenhouse.io/v1/boards/${n}/jobs`, j => j.jobs?.length);
  const lv = await probe(`https://api.lever.co/v0/postings/${n}?mode=json`, j => Array.isArray(j) && j.length);
  const ab = await probe(`https://api.ashbyhq.com/posting-api/job-board/${cap(n)}`, j => j.jobs?.length);
  const hits = [gh && `greenhouse:"${n}" (${gh})`, lv && `lever:"${n}" (${lv})`, ab && `ashby:"${cap(n)}" (${ab})`].filter(Boolean);
  console.log(`${n.padEnd(18)} ${hits.length ? hits.join('  ') : '— no public board found'}`);
}
