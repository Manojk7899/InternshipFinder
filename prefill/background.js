/*
 * Runs only when the toolbar button is clicked. There is no content script that sits on
 * pages in the background, and no host permissions in the manifest: activeTab grants
 * access to the one tab, for this one click, and nothing else.
 */
chrome.action.onClicked.addListener(async (tab) => {
  if (!tab || !tab.id) return;
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["matcher.js", "content.js"]
    });
  } catch (err) {
    // Chrome refuses injection on its own pages (chrome://, the Web Store). Nothing to
    // do about it and nothing worth interrupting the user over.
    console.warn("Prefill could not run on this page:", err && err.message);
  }
});

// First install: open the options page, since the extension does nothing without a profile.
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") chrome.runtime.openOptionsPage();
});
