# Mac Python Toolbox 🧰

A modular, terminal-based utility belt for macOS power users. Built with Python and [Rich](https://github.com/Textualize/rich) for a beautiful CLI experience.

## Features

### 🍺 Brew Manager
- **Audit & Update**: Smart updates that check for beta versions and outdated packages.
- **Search**: Enhanced search with top package trends and detailed info.
- **Cleanup**: Keep your Homebrew installation tidy.

### 🧹 System Cleaner
- **Junk Scan**: Find and remove user caches, logs, and trash to free up space.
- **Maintenance Tools**: Flush DNS, reindex Spotlight, free up RAM, and manage local Time Machine snapshots.

### ❤️ Health Doctor
- **System Vitals**: Quick view of hardware specs, uptime, and battery health.
- **Diagnostics**: Run network quality tests, check for macOS updates, and verify disk health.
- **Repairs**: Fix common issues like duplicate "Open With" entries or font cache corruption.

## Getting Started

### Prerequisites
- macOS
- Python 3.8+
- Homebrew (optional, but required for Brew Manager)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd brew-beta
   ```

2. Install dependencies:
   ```bash
   pip install rich
   ```

### Usage

Run the main toolbox:
```bash
python3 main.py
```

Navigate the menus using the number keys. Press **Enter** to go back or quit.

## Developer Documentation

Interested in adding your own tools? The system is designed to be easily extensible.
Check out our [Developer Guide](.github/copilot-instructions.md) for details on the module system and coding standards.
