function Header({ status, lastRefreshed }: { status?: string; lastRefreshed?: Date }) {
  const refreshLabel = lastRefreshed
    ? `↻ Updated at ${lastRefreshed.toUTCString().slice(17, 25)} UTC`
    : null;
  return (
    <header className="site-header">
      <div className="site-header-inner">
        <a
          href="https://velascommerce.com"
          className="site-header-logo"
          target="_blank"
          rel="noopener noreferrer"
        >
          <img src="/velas-logo.png" alt="Velas Commerce" className="site-header-logo-img" />
        </a>

        <div className="site-header-product">
          <div className="site-header-product-title">
            <img src="/lightning-pulse-logo.png" alt="Lightning Pulse" className="site-header-pulse-logo" />
            <span className="site-header-product-name">Lightning Pulse</span>
          </div>
          <span className="site-header-tagline">Real-time Bitcoin Lightning Network Analytics</span>
          {status && <span className="site-header-status">{status}</span>}
          {refreshLabel && <span className="site-header-refresh">{refreshLabel}</span>}
        </div>

        <a
          href="https://velascommerce.com"
          className="site-header-back"
          target="_blank"
          rel="noopener noreferrer"
        >
          velascommerce.com ↗
        </a>
      </div>
    </header>
  );
}

export default Header;
