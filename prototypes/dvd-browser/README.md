# DVD ISO browser connection prototype

This prototype checks whether a browser can read selected sectors from a
readable ISO on your computer. It uses Python 3 from Debian 12 or later and
serves the original bytes. DVD navigation and playback are future stages.

Run from the repository root, substituting the LAN IP of your computer:

```sh
python3 prototypes/dvd-browser/serve.py "/path/to/disc.iso" --bind 192.168.1.10
```

On an iPhone on the same network, open `http://192.168.1.10:8000/` in Safari
and tap **Test ISO connection**. The page requests two 2,048-byte sectors.
A successful result verifies byte-range access. The ISO 9660 signature is
reported when present. Use a trusted local network since the test endpoint
allows anyone who can reach it to read the selected ISO. Omit `--bind` to
test from the same computer at `http://127.0.0.1:8000/`.
