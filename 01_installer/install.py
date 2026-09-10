"""Install all dependencies: Python packages, Node.js/npm, and frontend build."""

import subprocess
import sys
import os
import shutil

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    # __file__ is not defined in interactive environments (e.g. CML notebook sessions)
    PROJECT_ROOT = os.getcwd()


def install_python_deps():
    """Install Python dependencies from requirements.txt."""
    req_file = os.path.join(PROJECT_ROOT, "requirements.txt")

    print("=" * 50)
    print("Installing Python dependencies...")
    print("=" * 50)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", req_file],
    )
    print("Python dependencies installed.\n")


def node_supported(version):
    parts = tuple(int(p) for p in version.strip().lstrip("v").split(".")[:3])
    return parts >= (22, 12, 0)


def initialize_config():
    config = os.path.join(PROJECT_ROOT, "config", "config.yaml")
    if not os.path.exists(config):
        shutil.copyfile(config + ".example", config)
        print("Created config/config.yaml from example")


def install_nodejs():
    """Install Node.js and npm via nvm if not already available."""
    print("=" * 50)
    print("Checking Node.js / npm...")
    print("=" * 50)

    nvm_dir = os.environ.get("NVM_DIR", os.path.expanduser("~/.nvm"))
    nvm_sh = os.path.join(nvm_dir, "nvm.sh")

    def run_with_nvm(cmd):
        """Run a command with nvm sourced."""
        return subprocess.check_output(
            ["bash", "-c", f'. "{nvm_sh}" && {cmd}'],
            text=True,
        ).strip()

    node_ok = shutil.which("node") is not None
    npm_ok = shutil.which("npm") is not None

    if not node_ok and os.path.isfile(nvm_sh):
        try:
            run_with_nvm("node --version")
            node_ok = npm_ok = True
        except Exception:
            pass

    if node_ok and npm_ok:
        try:
            node_ver = subprocess.check_output(["node", "--version"], text=True).strip()
            npm_ver = subprocess.check_output(["npm", "--version"], text=True).strip()
        except FileNotFoundError:
            node_ver = run_with_nvm("node --version")
            npm_ver = run_with_nvm("npm --version")
        if node_supported(node_ver):
            print(f"Node.js {node_ver} and npm {npm_ver} already installed.")
            if os.path.isfile(nvm_sh) and not shutil.which("node"):
                node_path = run_with_nvm("command -v node")
                os.environ["PATH"] = os.path.dirname(node_path) + os.pathsep + os.environ["PATH"]
            return
        print(f"Node {node_ver} is too old; installing Node 22 >= 22.12")

    node_major = "22"
    print(f"Node.js/npm not found. Installing Node.js {node_major}.x via nvm...")

    if not os.path.isfile(nvm_sh):
        print("Installing nvm...")
        subprocess.check_call(
            ["bash", "-c", "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash"],
        )
        if not os.path.isfile(nvm_sh):
            print("ERROR: nvm installation failed.")
            print("Please install Node.js manually: https://nodejs.org/")
            sys.exit(1)

    try:
        run_with_nvm(f"nvm install {node_major}")
        node_path = run_with_nvm("command -v node")
        os.environ["PATH"] = os.path.dirname(node_path) + os.pathsep + os.environ["PATH"]
        node_ver = run_with_nvm("node --version")
        assert node_supported(node_ver), node_ver
        npm_ver = run_with_nvm("npm --version")
        print(f"Node.js {node_ver} and npm {npm_ver} installed via nvm.")
    except Exception as e:
        print(f"Could not install Node.js via nvm: {e}")
        print("Please install Node.js manually: https://nodejs.org/")
        sys.exit(1)


def run_npm(args, cwd=None):
    """Run an npm command, sourcing nvm first if npm isn't on the system PATH."""
    if shutil.which("npm"):
        subprocess.check_call(["npm"] + args, cwd=cwd)
    else:
        nvm_dir = os.environ.get("NVM_DIR", os.path.expanduser("~/.nvm"))
        nvm_sh = os.path.join(nvm_dir, "nvm.sh")
        cmd = "npm " + " ".join(args)
        subprocess.check_call(["bash", "-c", f'. "{nvm_sh}" && {cmd}'], cwd=cwd)


def install_frontend():
    """Install npm dependencies and build the React frontend."""
    frontend_dir = os.path.join(PROJECT_ROOT, "03_frontend")
    pkg_json = os.path.join(frontend_dir, "package.json")

    if not os.path.isfile(pkg_json):
        print("WARNING: Frontend package.json not found, skipping frontend build.")
        return

    print("=" * 50)
    print("Installing frontend dependencies...")
    print("=" * 50)
    run_npm(["ci"], cwd=frontend_dir)

    print("\nBuilding frontend...")
    run_npm(["run", "build"], cwd=frontend_dir)
    print("Frontend built successfully.\n")


def create_directories():
    """Ensure data and model directories exist."""
    for d in ["data/raw", "data/processed", "models", "models/registry"]:
        path = os.path.join(PROJECT_ROOT, d)
        os.makedirs(path, exist_ok=True)
        print(f"  Directory ready: {d}")


def validate_resources():
    """Quick resource check."""
    print("=" * 50)
    print("Resource Validation")
    print("=" * 50)
    print(f"CPUs available: {os.cpu_count()}")
    disk = shutil.disk_usage(PROJECT_ROOT)
    print(f"Disk: {disk.free / (1024**3):.1f} GB free of {disk.total / (1024**3):.1f} GB")
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            print(f"GPU: {result.stdout.strip()}")
        else:
            print("GPU: None detected (CPU-only mode)")
    except FileNotFoundError:
        print("GPU: nvidia-smi not found (CPU-only mode)")
    print()


def main():
    validate_resources()

    print("=" * 50)
    print("Creating directories...")
    print("=" * 50)
    create_directories()
    print()

    initialize_config()
    install_python_deps()
    install_nodejs()
    install_frontend()

    print("=" * 50)
    print("Installation complete!")
    print("=" * 50)
    print()
    print("Next steps:")
    print("  1. Copy config: cp config/config.yaml.example config/config.yaml")
    print("     Then set your CAII endpoint in config/config.yaml")
    print("  2. Build data, DB, model & KB (first run only):")
    print("       python3 02_backend/data_generation/generate_synthetic_data.py")
    print("       python3 02_backend/scripts/prepare.py")
    print("  3. Start the app:   python3 start_app.py")


if __name__ == "__main__":
    assert node_supported("v22.12.0") and not node_supported("v18.20.0")
    main()
