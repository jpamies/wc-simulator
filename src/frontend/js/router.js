const Router = {
  routes: {},

  register(path, handler) {
    this.routes[path] = handler;
  },

  init() {
    window.addEventListener('hashchange', () => this.handleRoute());
    this.handleRoute();
  },

  handleRoute() {
    const hash = location.hash || '#/';
    const [path, queryStr] = hash.slice(1).split('?');
    const params = new URLSearchParams(queryStr || '');

    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(link => {
      const href = link.getAttribute('href');
      link.classList.toggle('active', path === href?.slice(1) || path.startsWith(href?.slice(1) + '/'));
    });

    // Find matching route (exact or pattern)
    for (const [route, handler] of Object.entries(this.routes)) {
      const match = this._match(route, path);
      if (match) {
        handler(match, params);
        return;
      }
    }

    // 404
    document.getElementById('app').innerHTML = `
      <div class="hero"><h1>404</h1><p>Página no encontrada</p></div>
    `;
  },

  _match(route, path) {
    const routeParts = route.split('/');
    const pathParts = path.split('/');
    if (routeParts.length !== pathParts.length) return null;

    const params = {};
    for (let i = 0; i < routeParts.length; i++) {
      if (routeParts[i].startsWith(':')) {
        params[routeParts[i].slice(1)] = decodeURIComponent(pathParts[i]);
      } else if (routeParts[i] !== pathParts[i]) {
        return null;
      }
    }
    return params;
  },
};
