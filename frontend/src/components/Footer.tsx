const SOCIAL_LINKS = [
  {
    label: "Nostr",
    href: "https://primal.net/p/nprofile1qqs02vdgvu465fq4kfc7sekmuy0mppjq7mqwtkv0jx9aqvyww95mtdcm8lzhh",
    path: "M3 3 L6.5 3 L18 17.5 L18 3 L21 3 L21 21 L17.5 21 L6 6.5 L6 21 L3 21 Z",
  },
  {
    label: "Twitter / X",
    href: "https://x.com/VelasCommerce",
    path: "M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.73-8.835L1.254 2.25H8.08l4.253 5.622 5.91-5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z",
  },
  {
    label: "LinkedIn",
    href: "https://linkedin.com/company/velascommerce",
    path: "M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6zM2 9h4v12H2z M4 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
  },
  {
    label: "YouTube",
    href: "https://www.youtube.com/channel/UCN0zbl1qUv9qEdaK1lzTWxg",
    path: "M22.54 6.42a2.78 2.78 0 0 0-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46a2.78 2.78 0 0 0-1.95 1.96A29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58A2.78 2.78 0 0 0 3.41 19.6C5.12 20 12 20 12 20s6.88 0 8.59-.46a2.78 2.78 0 0 0 1.95-1.95A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58zM9.75 15.02V8.98L15.5 12l-5.75 3.02z",
  },
];

function Footer() {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="site-footer-social">
          {SOCIAL_LINKS.map(({ label, href, path }) => (
            <a
              key={label}
              href={href}
              aria-label={label}
              className="site-footer-social-link"
              target="_blank"
              rel="noopener noreferrer"
            >
              <svg viewBox="0 0 24 24" fill="currentColor" width={18} height={18}>
                <path d={path} />
              </svg>
            </a>
          ))}
        </div>
        <p className="site-footer-copy">© {new Date().getFullYear()} Velas Investments LLC</p>
      </div>
    </footer>
  );
}

export default Footer;
