// The desktop version: a program on this computer instead of a site.
//
// Its server stops by itself when its last window is closed. It knows a window
// is open because every open page holds one quiet stream to it; this is that
// stream. The browser reconnects it by itself after a hiccup.
//
// A page the browser keeps for the Back button (its back/forward cache) is not
// open: the stream is let go when the page is hidden away like that and taken up
// again if the page comes back. A window that is only minimised keeps it.

let stream: EventSource | null = null;
let wanted = false;

function open() {
  if (stream || typeof EventSource === 'undefined') return;
  stream = new EventSource('/api/desktop/presence');
  stream.onerror = () => {
    // CLOSED means the server refused (signed out) rather than a dropped line: let a later call try again.
    if (stream && stream.readyState === EventSource.CLOSED) stream = null;
  };
}

export function holdDesktopOpen() {
  if (!wanted) {
    wanted = true;
    window.addEventListener('pagehide', () => { stream?.close(); stream = null; });
    window.addEventListener('pageshow', (e) => { if ((e as PageTransitionEvent).persisted) open(); });
  }
  open();
}
