document.addEventListener('DOMContentLoaded', () => {
  // Wait a short moment to ensure Prism.js has finished initial rendering
  setTimeout(() => {
    const preBlocks = document.querySelectorAll('pre');
    
    preBlocks.forEach(pre => {
      if (pre.querySelector('.copy-code-button')) return;
      
      const code = pre.querySelector('code');
      if (!code) return;
      
      const button = document.createElement('button');
      button.className = 'copy-code-button';
      button.type = 'button';
      button.ariaLabel = 'Copy code to clipboard';
      button.innerText = 'Copy';
      
      // Ensure pre is positioned relatively for button positioning
      pre.style.position = 'relative';
      
      pre.appendChild(button);
      
      button.addEventListener('click', () => {
        const text = code.textContent || '';
        
        navigator.clipboard.writeText(text).then(() => {
          button.innerText = 'Copied!';
          button.classList.add('copied');
          
          setTimeout(() => {
            button.innerText = 'Copy';
            button.classList.remove('copied');
          }, 2000);
        }).catch(err => {
          console.error('Could not copy text: ', err);
          button.innerText = 'Error';
        });
      });
    });
  }, 100);
});
