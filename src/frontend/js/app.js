// Register tournament-scoped versions of all pages
document.addEventListener('DOMContentLoaded', () => {
  // Get handlers from the already-registered routes
  const pageRoutes = ['/', '/calendar', '/standings', '/bracket', '/teams',
                      '/team/:code', '/player/:id', '/match/:id', '/simulate', '/stats',
                      '/squads', '/squad/:code'];
  for (const route of pageRoutes) {
    const handler = Router.routes[route];
    if (handler) {
      const subPath = route === '/' ? '/home' : route;
      registerTournamentPage(subPath, handler);
    }
  }

  Router.init();
});
