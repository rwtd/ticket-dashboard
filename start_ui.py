#!/usr/bin/env python3
"""
Startup script for Ticket Dashboard UI
Handles dependency checking and graceful startup
"""

import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = ['flask', 'pandas', 'matplotlib', 'seaborn']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n📦 Install missing packages with:")
        print("   pip install -r requirements.txt")
        return False
    
    return True

def main():
    """Main startup function"""
    print("🚀 Starting Ticket Dashboard UI...")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    print("✅ All dependencies found")
    
    # Check for data directories
    base_dir = Path(__file__).parent
    tickets_dir = base_dir / 'tickets'
    uploads_dir = base_dir / 'uploads'
    results_dir = base_dir / 'results'
    
    # Create directories if they don't exist
    for directory in [tickets_dir, uploads_dir, results_dir]:
        directory.mkdir(exist_ok=True)
        print(f"📁 Directory ready: {directory.name}/")
    
    # Check for existing ticket files
    ticket_files = list(tickets_dir.glob('*.csv'))
    if ticket_files:
        print(f"📋 Found {len(ticket_files)} existing ticket file(s)")
    else:
        print("📋 No existing ticket files found (you can upload via the UI)")
    
    print("\n🌐 Starting web server...")
    print("📍 URL: http://localhost:5000")
    print("🔧 Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Import and run Flask app
    try:
        import os
        from app import app
        
        # Get port from environment (Cloud Run sets PORT)
        port = int(os.environ.get('PORT', 5000))
        
        # Check if we're in production (Cloud Run)
        is_production = os.environ.get('FLASK_ENV') == 'production'
        
        if is_production:
            print(f"🌐 Starting production server on port {port}")
            app.run(debug=False, host='0.0.0.0', port=port)
        else:
            print(f"🔧 Starting development server on port {port}")
            app.run(debug=True, host='0.0.0.0', port=port)
            
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()