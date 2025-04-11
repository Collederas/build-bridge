document.addEventListener('DOMContentLoaded', function() {
    const siteHostname = window.location.hostname;
  
    // Find all links in the main content area (adjust selector if needed)
    // This selector tries to target links within common content wrappers
    // Excludes links within typical navigation/footer areas if possible
    const contentArea = document.querySelector('main article, .page__content, #main');
    const links = (contentArea || document.body).querySelectorAll('a');
  
    links.forEach(link => {
      try {
        const href = link.getAttribute('href');
        if (href) {
          if (href.startsWith('http://') || href.startsWith('https://')) {
            const linkUrl = new URL(href);
            if (linkUrl.hostname !== siteHostname) {
              link.setAttribute('target', '_blank');
              link.setAttribute('rel', 'noopener noreferrer');
            }
          }
        }
      } catch (e) {
        console.error("Could not process link:", link.href, e);
      }
    });
  });