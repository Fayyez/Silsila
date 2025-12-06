# liboqs Installation Guide

This guide provides step-by-step instructions for installing liboqs (Open Quantum Safe library) and its Python bindings on your local machine.

## Problem

The `liboqs-python` package version 0.14.1 tries to automatically install liboqs C library from a non-existent git branch (0.14.1). This causes the import to fail with:
```
RuntimeError: No oqs shared libraries found
```

## Solution Overview

We'll manually install liboqs version 0.14.0 (the latest available stable version) from source, which will then be found by the Python bindings.

---

## Prerequisites

### Windows
- Git for Windows: https://git-scm.com/download/win
- Visual Studio Build Tools or MinGW
- CMake: https://cmake.org/download/
- OpenSSL development libraries

### macOS
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install cmake openssl git
```

### Linux (Fedora/RHEL)
```bash
sudo dnf install gcc make cmake openssl-devel git
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install build-essential cmake libssl-dev git
```

---

## Step-by-Step Installation

### Step 1: Clone liboqs Repository

Open a terminal/command prompt and run:

```bash
cd /tmp  # or any temporary directory
git clone --branch 0.14.0 --depth 1 https://github.com/open-quantum-safe/liboqs
cd liboqs
```

**What this does:**
- `--branch 0.14.0`: Checks out the stable 0.14.0 release
- `--depth 1`: Downloads only the latest version (faster, smaller download)

### Step 2: Create Build Directory

```bash
mkdir build
cd build
```

### Step 3: Configure CMake Build

Run CMake to configure the build:

```bash
cmake -S .. -B . \
  -DBUILD_SHARED_LIBS=ON \
  -DOQS_BUILD_ONLY_LIB=ON \
  -DCMAKE_INSTALL_PREFIX=~/.oqs
```

**Flags explanation:**
- `-S ..`: Source directory (parent directory)
- `-B .`: Build directory (current directory)
- `-DBUILD_SHARED_LIBS=ON`: Build shared libraries (.so/.dll/.dylib)
- `-DOQS_BUILD_ONLY_LIB=ON`: Build only the library (skip tests/examples)
- `-CMAKE_INSTALL_PREFIX=~/.oqs`: Install to `~/.oqs` in your home directory

**Alternative install locations:**
- **Windows:** `-DCMAKE_INSTALL_PREFIX=C:\oqs`
- **macOS/Linux:** `-DCMAKE_INSTALL_PREFIX=/opt/oqs` (requires sudo install)

### Step 4: Build the Library

```bash
cmake --build . --parallel 4
```

**Notes:**
- `--parallel 4`: Uses 4 CPU cores (adjust based on your system)
- Build takes 5-15 minutes depending on hardware
- This will compile all the post-quantum algorithms

### Step 5: Install

```bash
cmake --build . --target install
```

**Verify installation:**
```bash
ls ~/.oqs/lib/
```

You should see `liboqs.so` (Linux), `liboqs.dylib` (macOS), or `oqs.dll` (Windows).

---

## Step 6: Configure Python Environment

Your Python environment needs to find the liboqs library. You have two options:

### Option A: Set Environment Variable (Recommended)

**Linux/macOS:**
```bash
export LD_LIBRARY_PATH=~/.oqs/lib:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=~/.oqs/lib64:$LD_LIBRARY_PATH  # For lib64 on some systems
```

**Windows (PowerShell):**
```powershell
$env:PATH = "C:\oqs\bin;$env:PATH"
```

**Windows (Command Prompt):**
```cmd
set PATH=C:\oqs\bin;%PATH%
```

**Make it Persistent:**

**Linux/macOS - Add to `~/.bashrc` or `~/.zshrc`:**
```bash
echo 'export LD_LIBRARY_PATH=~/.oqs/lib:~/.oqs/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

**Windows - Set System Environment Variable:**
1. Open Settings → Environment Variables
2. Click "New" → Create `OQS_INSTALL_PATH = C:\oqs`
3. Restart terminal/IDE

### Option B: Set OQS_INSTALL_PATH Variable

**Linux/macOS:**
```bash
export OQS_INSTALL_PATH=~/.oqs
```

**Add to `~/.bashrc` or `~/.zshrc`:**
```bash
echo 'export OQS_INSTALL_PATH=~/.oqs' >> ~/.bashrc
source ~/.bashrc
```

**Windows - Set System Environment Variable:**
1. Open Settings → Environment Variables
2. Click "New" → Create `OQS_INSTALL_PATH = C:\oqs`
3. Restart terminal/IDE

---

## Step 7: Test Installation

Activate your Python virtual environment (if using one):

```bash
# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

Test the import:

```bash
python -c "import oqs; print('OQS loaded successfully'); print('Version:', oqs.oqs_version())"
```

**Expected output:**
```
OQS loaded successfully
Version: 0.14.0
```

---

## Step 8: Verify liboqs-python Works

```bash
python << EOF
import oqs

# Test KEM (Key Encapsulation)
kem = oqs.KeyEncapsulation("ML-KEM-768")
public_key = kem.generate_keypair()
ciphertext, shared_secret = kem.encap_secret(public_key)
print(f"KEM test passed: {len(shared_secret)} byte shared secret generated")

# Test Signature
sig = oqs.Signature("ML-DSA-65")
public_key = sig.generate_keypair()
message = b"Hello, Quantum Safe World"
signature = sig.sign(message)
print(f"Signature test passed: {len(signature)} byte signature created")
print("All tests passed!")
EOF
```

---

## Troubleshooting

### Error: "CMake command not found"
**Solution:** Install CMake
- **Linux:** `sudo apt-get install cmake` or `sudo dnf install cmake`
- **macOS:** `brew install cmake`
- **Windows:** Download from https://cmake.org/download/

### Error: "No C compiler found"
**Solution:** Install build tools
- **Linux (Fedora):** `sudo dnf install gcc make`
- **Linux (Ubuntu):** `sudo apt-get install build-essential`
- **macOS:** `xcode-select --install`
- **Windows:** Install Visual Studio Build Tools

### Error: "OpenSSL not found"
**Solution:** Install OpenSSL development headers
- **Linux (Fedora):** `sudo dnf install openssl-devel`
- **Linux (Ubuntu):** `sudo apt-get install libssl-dev`
- **macOS:** `brew install openssl`
- **Windows:** Download from https://slproweb.com/products/Win32OpenSSL.html

### Error: "liboqs.so not found" after installation
**Solution:** 
1. Check installation path: `ls ~/.oqs/lib/`
2. Set environment variable: `export LD_LIBRARY_PATH=~/.oqs/lib:~/.oqs/lib64:$LD_LIBRARY_PATH`
3. Test: `python -c "import oqs"`

### Error: "Remote branch 0.14.1 not found"
**Solution:** This is the original problem. The issue is that `liboqs-python==0.14.1` tries to install 0.14.1 from git, but only 0.14.0 exists. By following this guide, you're installing 0.14.0 manually, which solves the problem.

---

## Using with Your Project

Once installed, your project should work:

```bash
# Activate venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Start your application
python app.py 5001
```

---

## Complete Quick Reference Script

### Linux/macOS

Create a file called `install_liboqs.sh`:

```bash
#!/bin/bash
set -e

echo "Installing liboqs from source..."

# Step 1: Clone repository
cd /tmp
git clone --branch 0.14.0 --depth 1 https://github.com/open-quantum-safe/liboqs
cd liboqs

# Step 2: Create build directory
mkdir -p build
cd build

# Step 3: Configure CMake
cmake -S .. -B . \
  -DBUILD_SHARED_LIBS=ON \
  -DOQS_BUILD_ONLY_LIB=ON \
  -DCMAKE_INSTALL_PREFIX=~/.oqs

# Step 4: Build
cmake --build . --parallel 4

# Step 5: Install
cmake --build . --target install

# Step 6: Set environment variables
export LD_LIBRARY_PATH=~/.oqs/lib:~/.oqs/lib64:$LD_LIBRARY_PATH
export OQS_INSTALL_PATH=~/.oqs

# Step 7: Verify
python -c "import oqs; print('✓ OQS installed successfully'); print('Version:', oqs.oqs_version())"

echo "Installation complete!"
echo "Add to ~/.bashrc or ~/.zshrc:"
echo "export LD_LIBRARY_PATH=~/.oqs/lib:~/.oqs/lib64:\$LD_LIBRARY_PATH"
echo "export OQS_INSTALL_PATH=~/.oqs"
```

Run it:
```bash
chmod +x install_liboqs.sh
./install_liboqs.sh
```

### Windows PowerShell

Create a file called `install_liboqs.ps1`:

```powershell
# Prerequisites: Git, CMake, Visual Studio Build Tools, OpenSSL should be installed

$OQS_PATH = "C:\oqs"

Write-Host "Installing liboqs from source..."

# Step 1: Clone repository
cd $env:TEMP
git clone --branch 0.14.0 --depth 1 https://github.com/open-quantum-safe/liboqs
cd liboqs

# Step 2: Create build directory
mkdir build -Force
cd build

# Step 3: Configure CMake
cmake -S .. -B . `
  -DBUILD_SHARED_LIBS=ON `
  -DOQS_BUILD_ONLY_LIB=ON `
  -DCMAKE_INSTALL_PREFIX=$OQS_PATH

# Step 4: Build
cmake --build . --parallel 4

# Step 5: Install
cmake --build . --target install

# Step 6: Set environment variables
$env:PATH = "$OQS_PATH\bin;$env:PATH"
[Environment]::SetEnvironmentVariable("OQS_INSTALL_PATH", $OQS_PATH, "User")

# Step 7: Verify
python -c "import oqs; print('✓ OQS installed successfully'); print('Version:', oqs.oqs_version())"

Write-Host "Installation complete!"
Write-Host "Restart your terminal for changes to take effect"
```

Run it:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\install_liboqs.sh
```

---

## Summary

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `git clone --branch 0.14.0 --depth 1 https://github.com/open-quantum-safe/liboqs` | Download source |
| 2 | `mkdir build && cd build` | Create build directory |
| 3 | `cmake -S .. -B . -DBUILD_SHARED_LIBS=ON -DOQS_BUILD_ONLY_LIB=ON -DCMAKE_INSTALL_PREFIX=~/.oqs` | Configure |
| 4 | `cmake --build . --parallel 4` | Build |
| 5 | `cmake --build . --target install` | Install |
| 6 | Set `LD_LIBRARY_PATH` or `OQS_INSTALL_PATH` | Configure path |
| 7 | `python -c "import oqs"` | Test |

---

## Additional Resources

- **liboqs GitHub:** https://github.com/open-quantum-safe/liboqs
- **liboqs-python GitHub:** https://github.com/open-quantum-safe/liboqs-python
- **OpenQS Documentation:** https://openquantumsafe.org/
- **ML-KEM (NIST FIPS 203):** Post-quantum key encapsulation mechanism
- **ML-DSA (NIST FIPS 204):** Post-quantum digital signature

---

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Verify all prerequisites are installed
3. Check CMake output for specific errors
4. Visit: https://github.com/open-quantum-safe/liboqs/discussions
