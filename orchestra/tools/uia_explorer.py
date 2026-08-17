import logging
from typing import List, Dict, Any, Optional

try:
    from pywinauto import Desktop
    from pywinauto.application import Application
except ImportError:
    Desktop = None
    Application = None

logger = logging.getLogger("orchestra.uia_explorer")

def get_clickable_elements(window_title: str) -> List[Dict[str, Any]]:
    """
    Finds a window by partial title and enumerates all clickable/interactive
    elements inside it using Windows UI Automation (UIA).
    
    Args:
        window_title: Partial or full title of the window.
        
    Returns:
        List of dictionaries representing interactive elements:
        {
            "name": str,
            "type": str,
            "rect": {"left": int, "top": int, "right": int, "bottom": int, "center_x": int, "center_y": int}
        }
    """
    if not Desktop:
        logger.error("pywinauto is not installed. UIA is unavailable.")
        return []

    try:
        desktop = Desktop(backend="uia")
        # Find window matching the title (case insensitive, partial match)
        windows = desktop.windows(title_re=f".*{window_title}.*", visible_only=True)
        if not windows:
            # Fallback to just partial matching if regex fails or is weird
            windows = desktop.windows(title=window_title, visible_only=True)
        
        if not windows:
            logger.warning(f"No visible window found matching title: '{window_title}'")
            return []
            
        target_window = windows[0]
        logger.info(f"UIA Explorer: Scanning window '{target_window.window_text()}'")
        
        elements = []
        # Filter for control types that are typically interactive
        interactive_types = {
            "ButtonControl", 
            "EditControl", 
            "MenuItemControl", 
            "ListItemControl", 
            "CheckBoxControl",
            "RadioButtonControl",
            "HyperlinkControl",
            "TabItemControl",
            "DocumentControl"
        }
        
        # Traverse descendants
        for desc in target_window.descendants():
            try:
                ctrl_type = desc.element_info.control_type
                if ctrl_type in interactive_types:
                    name = desc.window_text() or desc.element_info.name
                    if not name:
                        continue
                        
                    rect = desc.rectangle()
                    elements.append({
                        "name": name.strip(),
                        "type": ctrl_type.replace("Control", ""),
                        "rect": {
                            "left": rect.left,
                            "top": rect.top,
                            "right": rect.right,
                            "bottom": rect.bottom,
                            "center_x": rect.left + (rect.right - rect.left) // 2,
                            "center_y": rect.top + (rect.bottom - rect.top) // 2
                        }
                    })
            except Exception:
                continue
                
        return elements
    except Exception as e:
        logger.error(f"UIA Explorer encountered an error: {e}")
        return []
