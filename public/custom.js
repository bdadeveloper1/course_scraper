// custom.js

// Wait for the DOM to be fully loaded
document.addEventListener("DOMContentLoaded", function () {
    // Function to attempt to hide the watermark
    function hideWatermark() {
      // First, try to find the watermark in the main document
      let watermark = document.querySelector("a[href*='https://github.com/Chainlit/chainlit']");
      if (watermark) {
        watermark.style.display = "none";
      }
      // Next, try to find it inside the shadow DOM of #chainlit-copilot
      const chainlitCopilot = document.querySelector("#chainlit-copilot");
      if (chainlitCopilot && chainlitCopilot.shadowRoot) {
        const shadowWatermark = chainlitCopilot.shadowRoot.querySelector("a.watermark");
        if (shadowWatermark) {
          shadowWatermark.style.display = "none";
        }
      }
    }
  
    // Create an observer to watch for changes in the DOM (or shadow DOM)
    const observer = new MutationObserver(hideWatermark);
    observer.observe(document.body, { childList: true, subtree: true });
  
    // Run it once immediately
    hideWatermark();
  });
  