#!/usr/bin/env python3
"""
Export utilities for dashboard content
Supports PNG, PDF, and Google Docs export
"""

import os
import io
import base64
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_to_pdf(html_content: str, output_path: str) -> bool:
    """
    Export HTML content to PDF using WeasyPrint with JavaScript chart fallback
    
    Args:
        html_content: The HTML content to convert
        output_path: Path where PDF should be saved
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        import weasyprint
        import re
        
        # WeasyPrint can't render JavaScript charts, so we need to remove them
        # and replace with text summaries
        processed_content = _process_html_for_pdf(html_content)
        
        # Create PDF from processed HTML
        html_doc = weasyprint.HTML(string=processed_content)
        html_doc.write_pdf(output_path)
        
        logger.info(f"PDF exported successfully to {output_path}")
        return True
        
    except ImportError:
        logger.error("WeasyPrint not installed. Install with: pip install weasyprint")
        return False
    except Exception as e:
        logger.error(f"PDF export failed: {str(e)}")
        return False

def _process_html_for_pdf(html_content: str) -> str:
    """
    Process HTML content to make it compatible with WeasyPrint
    Removes JavaScript charts and replaces with text summaries
    """
    import re
    
    # Remove Plotly scripts and chart containers
    # Replace with placeholder text
    processed = re.sub(
        r'<script[^>]*plotly[^>]*>.*?</script>',
        '',
        html_content,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Remove script tags that reference Plotly
    processed = re.sub(
        r'<script[^>]*>.*?Plotly\.newPlot.*?</script>',
        '',
        processed,
        flags=re.DOTALL
    )
    
    # Replace chart containers with styled placeholders
    processed = re.sub(
        r'<div[^>]*plotly-graph-div[^>]*>.*?</div>',
        '<div class="chart-placeholder">'
        '<p>📊 Interactive Chart</p>'
        '<p style="font-size: 0.9em;">Visual charts available in web version and PNG exports.</p>'
        '</div>',
        processed,
        flags=re.DOTALL
    )
    
    # Also replace chart container divs that wrap plotly content
    processed = re.sub(
        r'<div[^>]*class="chart-container"[^>]*>.*?</div>',
        '<div class="chart-placeholder">'
        '<p>📊 Interactive Chart</p>'
        '<p style="font-size: 0.9em;">Visual charts available in web version and PNG exports.</p>'
        '</div>',
        processed,
        flags=re.DOTALL
    )
    
    # Replace any remaining chart divs
    processed = re.sub(
        r'<div[^>]*class="chart"[^>]*>.*?</div>',
        '<div class="chart-placeholder">'
        '<p>📊 Interactive Chart</p>'
        '<p style="font-size: 0.9em;">Visual charts available in web version and PNG exports.</p>'
        '</div>',
        processed,
        flags=re.DOTALL
    )
    
    # Replace weekly chart containers
    processed = re.sub(
        r'<div[^>]*weekly-chart-container[^>]*>.*?</div>',
        '<div class="chart-placeholder">'
        '<p>📊 Interactive Chart</p>'
        '<p style="font-size: 0.9em;">Visual charts available in web version and PNG exports.</p>'
        '</div>',
        processed,
        flags=re.DOTALL
    )
    
    # Remove any remaining script tags
    processed = re.sub(r'<script[^>]*>.*?</script>', '', processed, flags=re.DOTALL)
    
    # Remove external script references
    processed = re.sub(r'<script[^>]*src=[^>]*></script>', '', processed)
    
    # Add PDF-specific styling that maintains the dark theme
    pdf_css = """
    <style>
    @page {
        margin: 0.8in;
        background: linear-gradient(135deg, #0c0c0c 0%, #1a1a2e 50%, #16213e 100%);
        @top-center {
            content: "Dashboard Export";
            font-size: 10pt;
            color: #e0e0e0;
        }
        @bottom-right {
            content: "Page " counter(page);
            font-size: 9pt;
            color: #e0e0e0;
        }
    }
    
    /* Maintain dark theme for PDF */
    body {
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 11pt;
        line-height: 1.4;
        background: linear-gradient(135deg, #0c0c0c 0%, #1a1a2e 50%, #16213e 100%) !important;
        color: #e0e0e0 !important;
        margin: 0;
        padding: 20px;
    }
    
    /* Dark theme elements */
    .section {
        background: linear-gradient(145deg, #1e1e2e, #252538) !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        margin-bottom: 20px !important;
        padding: 15px !important;
        page-break-inside: avoid;
    }
    
    /* Colorful metric cards */
    .metric-card, .ticket-card {
        background: linear-gradient(135deg, #ff6b6b 0%, #ff8e53 100%) !important;
        color: white !important;
        border-radius: 8px !important;
        box-shadow: 0 3px 6px rgba(0,0,0,0.3) !important;
        display: inline-block !important;
        width: 180px !important;
        margin: 8px !important;
        padding: 15px !important;
        text-align: center !important;
        vertical-align: top !important;
    }
    
    .chat-card {
        background: linear-gradient(135deg, #4ecdc4 0%, #44a08d 100%) !important;
        color: white !important;
    }
    
    .weekend-card {
        background: linear-gradient(135deg, #ffeaa7 0%, #fab1a0 100%) !important;
        color: #2d3436 !important;
    }
    
    .bot-wynn-card {
        background: linear-gradient(135deg, #a29bfe 0%, #6c5ce7 100%) !important;
        color: white !important;
    }
    
    .bot-support-card, .transfer-card {
        background: linear-gradient(135deg, #fd79a8 0%, #e17055 100%) !important;
        color: white !important;
    }
    
    .success-card {
        background: linear-gradient(135deg, #00d4aa 0%, #36d1dc 100%) !important;
        color: white !important;
    }
    
    /* Headers */
    h1 {
        color: #ffffff !important;
        text-align: center !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5) !important;
        font-size: 2.2em !important;
        margin-bottom: 15px !important;
        page-break-after: avoid;
    }
    
    h2 {
        color: #00d4aa !important;
        font-size: 1.4em !important;
        margin: 15px 0 10px 0 !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3) !important;
        page-break-after: avoid;
    }
    
    h3 {
        color: #ff6b6b !important;
        margin: 10px 0 8px 0 !important;
        font-size: 1.2em !important;
        page-break-after: avoid;
    }
    
    /* Tables with dark theme */
    table {
        background: #2a2a3e !important;
        color: #e0e0e0 !important;
        border-collapse: collapse !important;
        width: 100% !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
        border-radius: 6px !important;
        overflow: hidden !important;
    }
    
    th {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        padding: 10px 8px !important;
        font-weight: bold !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        font-size: 10px !important;
        border: none !important;
    }
    
    td {
        padding: 8px !important;
        border-bottom: 1px solid #404040 !important;
        color: #e0e0e0 !important;
        font-size: 11px !important;
        border-left: none !important;
        border-right: none !important;
    }
    
    tr:nth-child(even) {
        background-color: rgba(255,255,255,0.02) !important;
    }
    
    /* Special styling for badges and highlights */
    .data-source-badge, .ticket-badge {
        background: linear-gradient(45deg, #ff6b6b, #ff8e53) !important;
        color: white !important;
        padding: 4px 12px !important;
        border-radius: 15px !important;
        font-size: 0.85em !important;
        margin: 0 3px !important;
        font-weight: bold !important;
        display: inline-block !important;
    }
    
    .chat-badge {
        background: linear-gradient(45deg, #4ecdc4, #44a08d) !important;
    }
    
    .combined-badge {
        background: linear-gradient(45deg, #ff6b6b, #4ecdc4) !important;
    }
    
    /* Date range styling */
    .date-range {
        background: linear-gradient(45deg, #ff6b6b, #4ecdc4) !important;
        color: white !important;
        padding: 6px 15px !important;
        border-radius: 20px !important;
        font-weight: bold !important;
        display: inline-block !important;
        margin: 8px 0 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
        font-size: 0.9em !important;
    }
    
    /* Chart placeholders with better styling */
    .chart-placeholder {
        background: linear-gradient(145deg, #2d3436, #636e72) !important;
        border: 2px solid rgba(0,212,170,0.3) !important;
        border-radius: 8px !important;
        padding: 20px !important;
        margin: 15px 0 !important;
        text-align: center !important;
    }
    
    .chart-placeholder p {
        color: #00d4aa !important;
        font-style: italic !important;
        font-size: 1.1em !important;
        margin: 8px 0 !important;
    }
    
    /* Metric values */
    .metric-value {
        font-size: 1.8em !important;
        font-weight: bold !important;
        margin: 6px 0 !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3) !important;
    }
    
    .metric-label {
        font-size: 0.85em !important;
        opacity: 0.9 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    
    /* Grid layout for metrics */
    .metric-grid {
        display: block !important;
        text-align: center !important;
    }
    
    /* Page breaks */
    .section {
        page-break-inside: avoid;
    }
    
    .performance-table {
        page-break-inside: auto;
    }
    
    .performance-table tr {
        page-break-inside: avoid;
    }
    </style>
    """
    
    # Insert PDF CSS before closing head tag
    processed = processed.replace('</head>', pdf_css + '</head>')
    
    return processed

def export_to_png(html_file_path: str, output_path: str, width: int = 1920, height: int = 1080) -> bool:
    """
    Export HTML file to PNG using Selenium WebDriver - captures full page with high quality
    
    Args:
        html_file_path: Path to the HTML file to capture
        output_path: Path where PNG should be saved
        width: Screenshot width in pixels
        height: Screenshot height in pixels
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time
        
        # Configure Chrome options for headless mode with high quality settings
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--hide-scrollbars")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-extensions")
        
        # High quality rendering settings
        chrome_options.add_argument("--force-device-scale-factor=2")  # 2x scaling for high DPI
        chrome_options.add_argument("--high-dpi-support")
        chrome_options.add_argument("--force-color-profile=srgb")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        
        # Set initial window size (will be adjusted later)
        chrome_options.add_argument(f"--window-size={width},{height}")
        
        # Initialize WebDriver
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            # Load the HTML file
            file_url = f"file://{os.path.abspath(html_file_path)}"
            driver.get(file_url)
            
            # Wait for page to load completely
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Wait for any Plotly charts to render
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script("return typeof Plotly !== 'undefined' ? window.Plotly._plots && Object.keys(window.Plotly._plots).length > 0 : true")
                )
            except:
                pass  # Continue if Plotly detection fails
            
            # Additional wait for dynamic content
            time.sleep(5)
            
            # Get more accurate page dimensions
            page_dimensions = driver.execute_script("""
                return {
                    scrollWidth: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
                    scrollHeight: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
                    clientWidth: Math.max(document.body.clientWidth, document.documentElement.clientWidth),
                    clientHeight: Math.max(document.body.clientHeight, document.documentElement.clientHeight),
                    offsetWidth: Math.max(document.body.offsetWidth, document.documentElement.offsetWidth),
                    offsetHeight: Math.max(document.body.offsetHeight, document.documentElement.offsetHeight)
                };
            """)
            
            # Calculate optimal dimensions
            total_width = max(page_dimensions['scrollWidth'], page_dimensions['offsetWidth'], width)
            total_height = max(page_dimensions['scrollHeight'], page_dimensions['offsetHeight'], height)
            
            # Add extra padding to prevent cutoff
            total_height += 100  # 100px bottom padding
            total_width += 50    # 50px right padding
            
            logger.info(f"Calculated page dimensions: {total_width}x{total_height}")
            
            # Set window size to capture full content with high DPI scaling
            driver.set_window_size(total_width, total_height)
            
            # Wait for resize to take effect
            time.sleep(2)
            
            # Scroll to ensure all content is loaded
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            driver.execute_script(f"window.scrollTo(0, {total_height});")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Take screenshot with high quality
            success = driver.save_screenshot(output_path)
            
            if success:
                # Post-process image to enhance quality if PIL is available
                try:
                    from PIL import Image, ImageEnhance
                    with Image.open(output_path) as img:
                        # Convert to RGB if necessary
                        if img.mode in ('RGBA', 'LA'):
                            # Create white background
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'RGBA':
                                background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                            else:
                                background.paste(img, mask=img.split()[-1])
                            img = background
                        
                        # Enhance image quality
                        enhancer = ImageEnhance.Sharpness(img)
                        img = enhancer.enhance(1.1)  # Slight sharpening
                        
                        enhancer = ImageEnhance.Contrast(img)
                        img = enhancer.enhance(1.05)  # Slight contrast boost
                        
                        # Save with high quality
                        img.save(output_path, 'PNG', optimize=True, quality=95)
                        
                except ImportError:
                    logger.info("PIL not available, skipping image enhancement")
                except Exception as enhance_error:
                    logger.warning(f"Image enhancement failed: {enhance_error}")
            
            logger.info(f"PNG exported successfully to {output_path} (Full page: {total_width}x{total_height})")
            return success
            
        finally:
            driver.quit()
            
    except ImportError:
        logger.error("Selenium not installed. Install with: pip install selenium")
        return False
    except Exception as e:
        logger.error(f"PNG export failed: {str(e)}")
        return False

def export_to_google_docs(html_content: str, document_title: str, credentials_path: Optional[str] = None) -> Optional[str]:
    """
    Export HTML content to Google Docs
    
    Args:
        html_content: The HTML content to convert
        document_title: Title for the Google Doc
        credentials_path: Path to Google API credentials JSON file
        
    Returns:
        str: Google Docs URL if successful, None otherwise
    """
    try:
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        
        # Scopes for Google Docs API
        SCOPES = ['https://www.googleapis.com/auth/documents']
        
        creds = None
        token_path = 'token.json'
        
        # Load existing credentials
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        # If no valid credentials, start OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_path:
                    credentials_path = 'credentials.json'
                
                if not os.path.exists(credentials_path):
                    logger.error(f"Google API credentials file not found: {credentials_path}")
                    logger.info("To enable Google Docs export:")
                    logger.info("1. Go to Google Cloud Console")
                    logger.info("2. Enable Google Docs API")
                    logger.info("3. Create OAuth 2.0 credentials")
                    logger.info("4. Add redirect URI: http://localhost:9090/")
                    logger.info("5. Download credentials.json to project root")
                    return None
                
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                # Use fixed port 9090 for consistent redirect URI
                creds = flow.run_local_server(port=9090, open_browser=True)
            
            # Save credentials for next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        # Build the service
        service = build('docs', 'v1', credentials=creds)
        
        # Create a new document
        document = {
            'title': document_title
        }
        
        doc = service.documents().create(body=document).execute()
        document_id = doc.get('documentId')
        
        # Convert HTML to structured Google Docs content
        try:
            requests = _convert_html_to_docs_requests(html_content)
            
            # Apply formatting requests to document
            if requests:
                service.documents().batchUpdate(
                    documentId=document_id,
                    body={'requests': requests}
                ).execute()
            else:
                # Fallback to simple text if no requests generated
                plain_text = _html_to_plain_text(html_content)
                service.documents().batchUpdate(
                    documentId=document_id,
                    body={'requests': [{'insertText': {'location': {'index': 1}, 'text': plain_text}}]}
                ).execute()
        except Exception as conversion_error:
            logger.error(f"Google Docs formatting failed, using plain text fallback: {str(conversion_error)}")
            # Simple fallback
            plain_text = _html_to_plain_text(html_content)
            service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': [{'insertText': {'location': {'index': 1}, 'text': plain_text}}]}
            ).execute()
        
        # Return the document URL
        doc_url = f"https://docs.google.com/document/d/{document_id}/edit"
        logger.info(f"Google Doc created successfully: {doc_url}")
        return doc_url
        
    except ImportError:
        logger.error("Google API client not installed. Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return None
    except Exception as e:
        logger.error(f"Google Docs export failed: {str(e)}")
        return None

def _html_to_plain_text(html_content: str) -> str:
    """
    Convert HTML to plain text as fallback
    """
    import re
    from html import unescape
    
    try:
        # Remove script tags completely
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
        title = ""
        if title_match:
            title = unescape(title_match.group(1).strip()) + "\n" + "="*50 + "\n\n"
        
        # Extract metric cards
        metrics_text = ""
        metric_cards = re.findall(r'<div[^>]*metric-value[^>]*>(.*?)</div>.*?<div[^>]*metric-label[^>]*>(.*?)</div>', html_content, re.DOTALL)
        if metric_cards:
            metrics_text = "KEY METRICS:\n"
            for value, label in metric_cards:
                value = unescape(re.sub(r'<[^>]+>', '', value)).strip()
                label = unescape(re.sub(r'<[^>]+>', '', label)).strip()
                metrics_text += f"• {label}: {value}\n"
            metrics_text += "\n"
        
        # Extract table data
        tables_text = ""
        table_matches = re.findall(r'<table[^>]*>(.*?)</table>', html_content, re.DOTALL)
        for table_html in table_matches:
            # Get headers
            header_match = re.search(r'<thead[^>]*>(.*?)</thead>', table_html, re.DOTALL)
            if header_match:
                headers = re.findall(r'<th[^>]*>(.*?)</th>', header_match.group(1), re.DOTALL)
                headers = [unescape(re.sub(r'<[^>]+>', '', h)).strip() for h in headers]
                
                if headers:
                    tables_text += "PERFORMANCE DATA:\n"
                    tables_text += " | ".join(headers) + "\n"
                    tables_text += "-" * (len(" | ".join(headers))) + "\n"
                    
                    # Get table rows
                    tbody_match = re.search(r'<tbody[^>]*>(.*?)</tbody>', table_html, re.DOTALL)
                    if tbody_match:
                        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_match.group(1), re.DOTALL)
                        for row in rows[:10]:  # Limit to first 10 rows
                            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                            cells = [unescape(re.sub(r'<[^>]+>', '', cell)).strip() for cell in cells]
                            if cells:
                                tables_text += " | ".join(cells) + "\n"
                    tables_text += "\n"
        
        # Simple text extraction for remaining content
        text_content = re.sub(r'<[^>]+>', '', html_content)
        text_content = unescape(text_content)
        text_content = re.sub(r'\s+', ' ', text_content)
        text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
        
        # Combine structured content
        result = title + metrics_text + tables_text
        
        if len(result.strip()) < 100:  # If we didn't extract much, include the plain text
            result += "\n\nADDITIONAL CONTENT:\n" + text_content[:2000]
        
        result += f"\n\n---\nGenerated by Ticket Analytics Dashboard\nExported on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return result
        
    except Exception as e:
        logger.error(f"Plain text conversion error: {str(e)}")
        return f"Dashboard Export\n\nExport error occurred. Please try again or use PNG/PDF export.\n\nError: {str(e)}"

def create_pdf_with_image(png_path: str, output_path: str, dashboard_type: str, timestamp: str) -> bool:
    """
    Create a PDF with embedded PNG image
    
    Args:
        png_path: Path to the PNG image
        output_path: Path where PDF should be saved
        dashboard_type: Type of dashboard for title
        timestamp: Timestamp for the report
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from PIL import Image as PILImage
        
        # Create PDF document
        doc = SimpleDocTemplate(output_path, pagesize=A4, 
                              rightMargin=72, leftMargin=72, 
                              topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#333333')
        )
        
        # Build story (content)
        story = []
        
        # Add title
        title_text = f"{dashboard_type.title()} Analytics Dashboard"
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 12))
        
        # Add timestamp
        timestamp_style = ParagraphStyle(
            'Timestamp',
            parent=styles['Normal'],
            fontSize=10,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#666666')
        )
        story.append(Paragraph(f"Generated on {timestamp.replace('_', ' at ')}", timestamp_style))
        story.append(Spacer(1, 20))
        
        # Add the dashboard image
        # Get image dimensions and scale to fit page
        with PILImage.open(png_path) as img:
            img_width, img_height = img.size
            
        # Calculate scaling to fit page width (minus margins)
        page_width = A4[0] - 144  # A4 width minus left/right margins
        page_height = A4[1] - 200  # A4 height minus top/bottom margins and title space
        
        scale_width = page_width / img_width
        scale_height = page_height / img_height
        scale = min(scale_width, scale_height)
        
        scaled_width = img_width * scale
        scaled_height = img_height * scale
        
        # Add image
        img = Image(png_path, width=scaled_width, height=scaled_height)
        story.append(img)
        story.append(Spacer(1, 20))
        
        # Add footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#888888')
        )
        story.append(Paragraph("Generated by Ticket Analytics Dashboard", footer_style))
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"PDF with embedded image created successfully: {output_path}")
        return True
        
    except ImportError:
        logger.error("ReportLab not installed. Install with: pip install reportlab")
        return False
    except Exception as e:
        logger.error(f"PDF image embedding failed: {str(e)}")
        return False

def create_google_doc_with_image(png_path: str, document_title: str, credentials_path: Optional[str] = None) -> Optional[str]:
    """
    Create a Google Doc with embedded PNG image
    
    Args:
        png_path: Path to the PNG image
        document_title: Title for the Google Doc
        credentials_path: Path to Google API credentials
        
    Returns:
        str: Google Docs URL if successful, None otherwise
    """
    try:
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        import base64
        
        # Scopes for Google Docs and Drive APIs
        SCOPES = [
            'https://www.googleapis.com/auth/documents',
            'https://www.googleapis.com/auth/drive.file'
        ]
        
        creds = None
        token_path = 'token.json'
        
        # Load existing credentials
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        # If no valid credentials, start OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_path:
                    credentials_path = 'credentials.json'
                
                if not os.path.exists(credentials_path):
                    logger.error("Google API credentials not found")
                    return None
                
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=9090, open_browser=True)
            
            # Save credentials for next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        # Build the services
        docs_service = build('docs', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        
        # First, upload image to Google Drive
        image_metadata = {
            'name': f'dashboard_image_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png',
            'parents': []  # Store in root folder
        }
        
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(png_path, mimetype='image/png')
        
        image_file = drive_service.files().create(
            body=image_metadata,
            media_body=media,
            fields='id,webViewLink'
        ).execute()
        
        image_file_id = image_file.get('id')
        
        # Make image publicly viewable
        drive_service.permissions().create(
            fileId=image_file_id,
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
        
        # Create a new Google Doc
        document = {
            'title': document_title
        }
        
        doc = docs_service.documents().create(body=document).execute()
        document_id = doc.get('documentId')
        
        # Insert content into the document
        requests = [
            # Insert title
            {
                'insertText': {
                    'location': {'index': 1},
                    'text': f'{document_title}\n\n'
                }
            },
            # Format title
            {
                'updateTextStyle': {
                    'range': {
                        'startIndex': 1,
                        'endIndex': len(document_title) + 1
                    },
                    'textStyle': {
                        'fontSize': {'magnitude': 18, 'unit': 'PT'},
                        'bold': True
                    },
                    'fields': 'fontSize,bold'
                }
            },
            # Center title
            {
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': 1,
                        'endIndex': len(document_title) + 1
                    },
                    'paragraphStyle': {
                        'alignment': 'CENTER'
                    },
                    'fields': 'alignment'
                }
            },
            # Insert image
            {
                'insertInlineImage': {
                    'location': {'index': len(document_title) + 3},
                    'uri': f'https://drive.google.com/uc?id={image_file_id}',
                    'objectSize': {
                        'height': {'magnitude': 400, 'unit': 'PT'},
                        'width': {'magnitude': 600, 'unit': 'PT'}
                    }
                }
            }
        ]
        
        # Add footer
        footer_text = f'\n\nGenerated by Ticket Analytics Dashboard on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        requests.append({
            'insertText': {
                'location': {'index': len(document_title) + 3},
                'text': footer_text
            }
        })
        
        # Apply all requests
        docs_service.documents().batchUpdate(
            documentId=document_id,
            body={'requests': requests}
        ).execute()
        
        # Return the document URL
        doc_url = f"https://docs.google.com/document/d/{document_id}/edit"
        logger.info(f"Google Doc with embedded image created successfully: {doc_url}")
        return doc_url
        
    except ImportError:
        logger.error("Google API client not installed")
        return None
    except Exception as e:
        logger.error(f"Google Docs image embedding failed: {str(e)}")
        return None

def _convert_html_to_docs_requests(html_content: str) -> List[Dict]:
    """
    Convert HTML content to Google Docs API requests
    
    Args:
        html_content: HTML content from dashboard
        
    Returns:
        List of Google Docs API requests for formatting
    """
    import re
    from html import unescape
    import json
    
    requests = []
    current_index = 1
    
    try:
        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', html_content, re.DOTALL)
        if title_match:
            title = unescape(title_match.group(1).strip())
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': title + '\n\n'
                }
            })
            # Format as title (large, bold, centered)
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(title)
                    },
                    'textStyle': {
                        'fontSize': {'magnitude': 24, 'unit': 'PT'},
                        'bold': True
                    },
                    'fields': 'fontSize,bold'
                }
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(title)
                    },
                    'paragraphStyle': {
                        'alignment': 'CENTER'
                    },
                    'fields': 'alignment'
                }
            })
            current_index += len(title) + 2
        
        # Extract and format metric cards
        metric_cards = re.findall(r'<div[^>]*metric-card[^>]*>.*?<div[^>]*metric-value[^>]*>(.*?)</div>.*?<div[^>]*metric-label[^>]*>(.*?)</div>.*?</div>', html_content, re.DOTALL)
        
        if metric_cards:
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': '📊 KEY METRICS\n\n'
                }
            })
            # Format as heading
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + 16
                    },
                    'textStyle': {
                        'fontSize': {'magnitude': 16, 'unit': 'PT'},
                        'bold': True
                    },
                    'fields': 'fontSize,bold'
                }
            })
            current_index += 18
            
            for value, label in metric_cards:
                value = unescape(re.sub(r'<[^>]+>', '', value)).strip()
                label = unescape(re.sub(r'<[^>]+>', '', label)).strip()
                
                metric_text = f"• {label}: {value}\n"
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': metric_text
                    }
                })
                current_index += len(metric_text)
            
            current_index += 1
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': '\n'
                }
            })
            current_index += 1
        
        # Extract and format tables
        table_matches = re.findall(r'<table[^>]*>(.*?)</table>', html_content, re.DOTALL)
        for table_html in table_matches:
            # Extract table headers
            header_match = re.search(r'<thead[^>]*>(.*?)</thead>', table_html, re.DOTALL)
            if header_match:
                headers = re.findall(r'<th[^>]*>(.*?)</th>', header_match.group(1), re.DOTALL)
                headers = [unescape(re.sub(r'<[^>]+>', '', h)).strip() for h in headers]
                
                # Extract table rows
                tbody_match = re.search(r'<tbody[^>]*>(.*?)</tbody>', table_html, re.DOTALL)
                if tbody_match:
                    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_match.group(1), re.DOTALL)
                    table_data = []
                    for row in rows:
                        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                        cells = [unescape(re.sub(r'<[^>]+>', '', cell)).strip() for cell in cells]
                        if cells:  # Skip empty rows
                            table_data.append(cells)
                    
                    if headers and table_data:
                        # Add table title
                        requests.append({
                            'insertText': {
                                'location': {'index': current_index},
                                'text': '📋 PERFORMANCE DATA\n\n'
                            }
                        })
                        # Format as heading
                        requests.append({
                            'updateTextStyle': {
                                'range': {
                                    'startIndex': current_index,
                                    'endIndex': current_index + 21
                                },
                                'textStyle': {
                                    'fontSize': {'magnitude': 16, 'unit': 'PT'},
                                    'bold': True
                                },
                                'fields': 'fontSize,bold'
                            }
                        })
                        current_index += 23
                        
                        # Insert table
                        table_request = {
                            'insertTable': {
                                'location': {'index': current_index},
                                'rows': len(table_data) + 1,  # +1 for headers
                                'columns': len(headers)
                            }
                        }
                        requests.append(table_request)
                        
                        # Calculate table end index (rough estimate)
                        table_size = (len(headers) * len(table_data)) * 2  # Rough estimate for cells
                        current_index += table_size + 10
                        
                        # Insert header data
                        for i, header in enumerate(headers):
                            requests.append({
                                'insertText': {
                                    'location': {'index': current_index + i * 2},
                                    'text': header
                                }
                            })
                        
                        # Insert row data (simplified - in real implementation would need precise cell indexing)
                        for row_data in table_data[:5]:  # Limit to first 5 rows
                            for cell in row_data:
                                requests.append({
                                    'insertText': {
                                        'location': {'index': current_index},
                                        'text': str(cell)
                                    }
                                })
                                current_index += len(str(cell)) + 2
                        
                        current_index += 20
        
        # Extract sections and headings
        sections = re.findall(r'<h2[^>]*>(.*?)</h2>', html_content)
        for section in sections:
            section_text = unescape(re.sub(r'<[^>]+>', '', section)).strip()
            if section_text and 'Analytics Charts' not in section_text:  # Skip chart sections
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': f'\n{section_text}\n\n'
                    }
                })
                # Format as heading
                requests.append({
                    'updateTextStyle': {
                        'range': {
                            'startIndex': current_index + 1,
                            'endIndex': current_index + len(section_text) + 1
                        },
                        'textStyle': {
                            'fontSize': {'magnitude': 14, 'unit': 'PT'},
                            'bold': True
                        },
                        'fields': 'fontSize,bold'
                    }
                })
                current_index += len(section_text) + 4
        
        # Add chart placeholders
        chart_sections = re.findall(r'<div[^>]*class="chart[^"]*"[^>]*>', html_content)
        if chart_sections:
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': '\n📊 VISUAL CHARTS\n\n'
                }
            })
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': current_index + 1,
                        'endIndex': current_index + 17
                    },
                    'textStyle': {
                        'fontSize': {'magnitude': 16, 'unit': 'PT'},
                        'bold': True
                    },
                    'fields': 'fontSize,bold'
                }
            })
            current_index += 19
            
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': 'Interactive charts and visualizations are available in the web dashboard.\n\nThis Google Docs version contains the summary data and metrics shown above.\n\n'
                }
            })
            current_index += 140
        
        # Add footer
        requests.append({
            'insertText': {
                'location': {'index': current_index},
                'text': f'\n\n---\nGenerated by Ticket Analytics Dashboard\nExported on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            }
        })
        
        return requests
        
    except Exception as e:
        logger.error(f"Error converting HTML to Google Docs format: {str(e)}")
        # Fallback to simple text
        from html import unescape
        import re
        plain_text = re.sub('<[^<]+?>', '', html_content)
        plain_text = unescape(plain_text)
        plain_text = re.sub(r'\n\s*\n', '\n\n', plain_text)
        
        return [{
            'insertText': {
                'location': {'index': 1},
                'text': plain_text
            }
        }]

class DashboardExporter:
    """Handles export operations for dashboard content"""
    
    def __init__(self, results_dir: Path):
        self.results_dir = Path(results_dir)
        
    def export_dashboard(self, dashboard_type: str, export_format: str, **kwargs) -> Dict[str, Any]:
        """
        Export dashboard in specified format
        
        Args:
            dashboard_type: Type of dashboard ('ticket', 'chat', 'combined')
            export_format: Export format ('png', 'pdf', 'google_docs')
            **kwargs: Additional parameters for specific exporters
            
        Returns:
            Dict with success status and file path or URL
        """
        dashboard_files = {
            'ticket': 'ticket_analytics_dashboard.html',
            'chat': 'chat_analytics_dashboard.html', 
            'combined': 'index.html'
        }
        
        dashboard_file = self.results_dir / dashboard_files.get(dashboard_type, 'index.html')
        
        if not dashboard_file.exists():
            return {
                'success': False,
                'error': f"Dashboard file not found: {dashboard_file}"
            }
        
        # Generate output filename
        timestamp = self.results_dir.name
        base_name = f"{dashboard_type}_dashboard_{timestamp}"
        
        if export_format == 'png':
            output_path = self.results_dir / f"{base_name}.png"
            # Filter kwargs for PNG export (only width/height are supported)
            png_kwargs = {k: v for k, v in kwargs.items() if k in ['width', 'height']}
            success = export_to_png(str(dashboard_file), str(output_path), **png_kwargs)
            return {
                'success': success,
                'file_path': str(output_path) if success else None,
                'format': 'PNG'
            }
            
        elif export_format == 'pdf':
            output_path = self.results_dir / f"{base_name}.pdf"
            
            # Generate PNG first, then embed in PDF
            png_path = self.results_dir / f"{base_name}_temp.png"
            # Filter kwargs for PNG export (only width/height are supported)
            png_kwargs = {k: v for k, v in kwargs.items() if k in ['width', 'height']}
            png_success = export_to_png(str(dashboard_file), str(png_path), **png_kwargs)
            
            if png_success:
                # Create PDF with embedded PNG
                success = create_pdf_with_image(str(png_path), str(output_path), dashboard_type, timestamp)
                # Clean up temporary PNG
                if png_path.exists():
                    png_path.unlink()
            else:
                # Fallback to HTML-based PDF
                with open(dashboard_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                success = export_to_pdf(html_content, str(output_path))
            
            return {
                'success': success,
                'file_path': str(output_path) if success else None,
                'format': 'PDF'
            }
            
        elif export_format == 'google_docs':
            # Generate PNG first, then embed in Google Docs
            png_path = self.results_dir / f"{base_name}_temp.png"
            # Filter kwargs for PNG export (only width/height are supported)
            png_kwargs = {k: v for k, v in kwargs.items() if k in ['width', 'height']}
            png_success = export_to_png(str(dashboard_file), str(png_path), **png_kwargs)
            
            if png_success:
                doc_title = f"{dashboard_type.title()} Analytics Dashboard - {timestamp}"
                # Filter kwargs for Google Docs export (only credentials_path is supported)
                gdocs_kwargs = {k: v for k, v in kwargs.items() if k == 'credentials_path'}
                doc_url = create_google_doc_with_image(str(png_path), doc_title, **gdocs_kwargs)
                # Clean up temporary PNG
                if png_path.exists():
                    png_path.unlink()
            else:
                # Fallback to HTML-based export
                with open(dashboard_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                doc_title = f"{dashboard_type.title()} Analytics Dashboard - {timestamp}"
                gdocs_kwargs = {k: v for k, v in kwargs.items() if k == 'credentials_path'}
                doc_url = export_to_google_docs(html_content, doc_title, **gdocs_kwargs)
            
            return {
                'success': doc_url is not None,
                'url': doc_url,
                'format': 'Google Docs'
            }
            
        else:
            return {
                'success': False,
                'error': f"Unsupported export format: {export_format}"
            }