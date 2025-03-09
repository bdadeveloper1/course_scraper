// Wait for the DOM to be fully loaded
document.addEventListener("DOMContentLoaded", function () {
  function removeUnwantedUI() {
      // Find and remove the new chat button
      let newChatButton = document.querySelector('[data-testid="components.molecules.newChatButton.newChat"]');
      if (newChatButton) {
          newChatButton.style.display = "none";
      }

      // Remove other unwanted UI elements (example)
      let elementsToRemove = document.querySelectorAll("[data-testid*='components.']");
      elementsToRemove.forEach(el => el.style.display = "none");
  }

  // Observe the DOM for any new UI elements being added
  const observer = new MutationObserver(removeUnwantedUI);
  observer.observe(document.body, { childList: true, subtree: true });

  // Run the function immediately
  removeUnwantedUI();
});
