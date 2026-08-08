# Call Deck — build tooling
Static call-deck app. `index.html` (built from `src/template.html`) fetches `leads.enc`
(AES-256-GCM: 12-byte IV + ciphertext) and decrypts client-side with a key passed once
via the URL fragment. No lead data or keys live in this repo. Build config and secrets
are stored privately in the owner's Drive ("call-deck-config.json").
