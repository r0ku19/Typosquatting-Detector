const BACKEND_URL = "http://127.0.0.1:5000/check-url";
const DEFAULT_TEST_URL = "https://ph1lhealth.gov.ph/login";

const urlInput = document.getElementById("urlInput");
const scanButton = document.getElementById("scanButton");
const resultBox = document.getElementById("resultBox");
const activeTabLabel = document.getElementById("activeTabLabel");

function renderResult(message, variant, details = "") {
  resultBox.className = `result ${variant}`;
  resultBox.innerHTML = `
    <strong>${message}</strong>
    <div class="meta">${details}</div>
  `;
}

async function scanUrl() {
  const targetUrl = urlInput.value.trim();

  if (!targetUrl) {
    renderResult("Enter a URL before scanning.", "warning");
    return;
  }

  scanButton.disabled = true;
  scanButton.textContent = "Scanning...";
  resultBox.className = "result";
  resultBox.textContent = "";

  try {
    const response = await fetch(BACKEND_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url: targetUrl }),
    });

    const payload = await response.json();

    if (!response.ok) {
      const errorMessage = payload.error || "The backend returned an error.";
      renderResult("Scan failed.", "warning", errorMessage);
      return;
    }

    if (payload.is_typosquat) {
      renderResult(
        "Security warning: possible typosquat detected.",
        "warning",
        `Closest legitimate domain: ${payload.matched_domain || "unknown"} | Similarity score: ${payload.similarity_score}`
      );
      return;
    }

    renderResult(
      "No typosquatting risk detected.",
      "safe",
      `Closest legitimate domain: ${payload.matched_domain || "unknown"} | Similarity score: ${payload.similarity_score}`
    );
  } catch (error) {
    renderResult("Unable to reach the local detector.", "warning", error.message);
  } finally {
    scanButton.disabled = false;
    scanButton.textContent = "Scan URL";
  }
}

async function loadActiveTabUrl() {
  try {
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const activeUrl = activeTab?.url || DEFAULT_TEST_URL;
    urlInput.value = activeUrl;
    activeTabLabel.textContent = `Active tab: ${activeUrl}`;
  } catch (error) {
    urlInput.value = DEFAULT_TEST_URL;
    activeTabLabel.textContent = "Active tab unavailable; using demo URL.";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  scanButton.addEventListener("click", scanUrl);
  urlInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      scanUrl();
    }
  });
  loadActiveTabUrl();
});