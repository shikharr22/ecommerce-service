#!/usr/bin/env python3
"""
Development setup script for the e-commerce service

This script helps set up the development environment and run basic tests.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"📋 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        return None

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")

def setup_virtual_environment():
    """Set up virtual environment if it doesn't exist"""
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("🔧 Creating virtual environment...")
        run_command("python3 -m venv .venv", "Virtual environment creation")
        print("💡 Activate with: source .venv/bin/activate")
    else:
        print("✅ Virtual environment already exists")

def install_dependencies():
    """Install project dependencies"""
    # Check if we're in a virtual environment
    in_venv = sys.prefix != sys.base_prefix
    pip_cmd = "pip" if in_venv else "python3 -m pip"
    
    print(f"📦 Installing dependencies using {pip_cmd}...")
    return run_command(f"{pip_cmd} install -r requirements.txt", "Dependency installation")

def test_imports():
    """Test critical imports"""
    print("🧪 Testing critical imports...")
    try:
        import flask
        import sqlalchemy
        import psycopg2
        print("✅ Core dependencies imported successfully")
        print(f"  - Flask: {flask.__version__}")
        print(f"  - SQLAlchemy: {sqlalchemy.__version__}")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def run_syntax_check():
    """Run syntax check on main application file"""
    return run_command("python3 -m py_compile src/main.py", "Syntax check")

def show_next_steps():
    """Show next steps for development"""
    print("\n🎉 Setup completed! Next steps:")
    print("\n1. 🐘 Set up PostgreSQL database:")
    print("   - Install PostgreSQL")
    print("   - Create database: createdb ecommerce_dev")
    print("   - Run migrations: python src/db.py")
    
    print("\n2. 🔧 Configure environment:")
    print("   - Copy .env.example to .env (if available)")
    print("   - Set DATABASE_URL=postgresql://user:pass@localhost:5432/ecommerce_dev")
    
    print("\n3. 🚀 Start the development server:")
    print("   - python src/main.py")
    print("   - API will be available at http://localhost:5000")
    
    print("\n4. 🧪 Test the API:")
    print("   - GET http://localhost:5000/health")
    print("   - GET http://localhost:5000/products")
    print("   - Remember to add X-User-Id header for cart operations")
    
    print("\n📚 Documentation:")
    print("   - API docs will be at http://localhost:5000/docs (once implemented)")
    print("   - Health check: http://localhost:5000/health")

def main():
    print("🔧 E-commerce Service Development Setup")
    print("=" * 40)
    
    # Change to project directory
    os.chdir(Path(__file__).parent)
    
    # Run setup steps
    check_python_version()
    setup_virtual_environment()
    
    # Try to install dependencies
    if install_dependencies():
        if test_imports():
            if run_syntax_check():
                print("\n✅ All checks passed!")
                show_next_steps()
            else:
                print("\n❌ Syntax check failed")
        else:
            print("\n❌ Import test failed")
    else:
        print("\n❌ Dependency installation failed")
        print("\n💡 Try:")
        print("  1. Activate virtual environment: source .venv/bin/activate")
        print("  2. Upgrade pip: pip install --upgrade pip")
        print("  3. Install dependencies: pip install -r requirements.txt")

if __name__ == "__main__":
    main()