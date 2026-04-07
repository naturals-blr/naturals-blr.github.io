#!/usr/bin/env python3
"""
Update Store Template with Enhanced Review System
Replaces the current store.html.j2 with store-enhanced.html.j2
"""

import os
import shutil
from pathlib import Path

def update_store_template():
    """Replace store.html.j2 with enhanced version"""
    
    # Paths
    build_dir = Path(__file__).parent
    template_dir = build_dir / "templates"
    
    # Source and destination
    enhanced_template = template_dir / "store-enhanced.html.j2"
    original_template = template_dir / "store.html.j2"
    
    # Backup original
    if original_template.exists():
        backup_path = template_dir / "store.html.j2.backup"
        shutil.copy2(original_template, backup_path)
        print(f"✅ Backed up original template to: {backup_path}")
    
    # Replace with enhanced version
    if enhanced_template.exists():
        shutil.copy2(enhanced_template, original_template)
        print(f"✅ Updated store template with enhanced review system")
        print(f"📝 Source: {enhanced_template}")
        print(f"📝 Target: {original_template}")
    else:
        print(f"❌ Enhanced template not found: {enhanced_template}")
        return False
    
    return True

if __name__ == "__main__":
    print("🌿 Updating Store Template with Enhanced Review System")
    print("=" * 50)
    
    success = update_store_template()
    
    if success:
        print("\n✅ Store template updated successfully!")
        print("\n🎯 Enhanced Features:")
        print("   • Review snippets (latest 4 reviews)")
        print("   • 'Read All 5-Star Reviews' button")
        print("   • Wall of Love modal with lazy loading")
        print("   • Mobile-first responsive design")
        print("   • Performance optimized with batch loading")
        print("\n📱 Mobile Optimizations:")
        print("   • Easy tap-to-close button")
        print("   • Scrollable modal container")
        print("   • Touch-friendly interface")
        print("\n🚀 Ready for next build!")
    else:
        print("\n❌ Failed to update store template")
