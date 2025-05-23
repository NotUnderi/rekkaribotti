
<h1 align="center">RekkariBotti 🚗🇫🇮</h1>

<p align="center">
  🔍 Fetch Finnish vehicle data by license plate, fast and easy.<br>
  Caches lookups locally for performance.<br>
</p>

<p align="center">
  <a href="https://github.com/NotUnderi/rekkaribotti/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/NotUnderi/rekkaribotti" alt="MIT License"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/Made%20with-%E2%9D%A4-red?style=flat-square" alt="Made with Love">
</p>

**RekkariBotti** is a simple bot designed to fetch Finnish vehicle information by license plate using an Biltema's API. Useful for quick lookups, integrations, or just for fun.

## Features

- 🔍 Lookup vehicle data by Finnish license plate  
- 📦 Lightweight and easy to run  
- 🧠 Parses and formats vehicle info into human-readable output
- 🗂️ Caches previously checked license plates locally for faster future access


## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/NotUnderi/rekkaribotti.git
   cd rekkaribotti
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   
3. Create .env file in the same directory and add your Discord bot token.
   ```bash
   echo "DISCORD_TOKEN=yourtokenhere" > .env
   ```

## Usage

```bash
python3 rekkaribotti.py
```

The bot should now be running on your server ready to read license plates!

## TODO

- [ ] Docker container for easy deployment  
- [ ] Integrate Traficom Open Data to find/predict car location, weight etc. and get power/weight for comparing cars
- [ ] Full rewrite to standardize variable and other names from Finnish to English and make the bot and fetching/caching script seperate

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Made with ❤️ in Finland by [NotUnderi](https://github.com/NotUnderi)

---
