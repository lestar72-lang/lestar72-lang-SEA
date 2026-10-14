import os
import smtplib
import traceback
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from playwright.sync_api import sync_playwright

TARGET_URL = "https://gfiber.com/webpass/signup/"

LOCATIONS = [
    {
        "address": "18 10th Street San Francisco CA 94103",
        "unit": "224",
        "prefix": "sf",
        "label": "San Francisco"
    },
    {
        "address": "501 Roy Street Seattle WA 98109",
        "unit": "216",
        "prefix": "sea",
        "label": "Seattle"
    }
]

DEFAULT_SENDER = "lestar72@gmail.com"
DEFAULT_RECIPIENTS = "rgalvin@gfiber.com, lestar72@gmail.com"

def run_agent():
    print("=== STARTING AGENT RUN ===")
    captured_screenshots = []
    email_body_text = "GFiber Webpass 3-Day Appointment Schedule Report\n\n"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--window-size=1440,900"
            ]
        )

        for loc in LOCATIONS:
            print(f"\n--- Processing Location: {loc['label']} ({loc['address']} #{loc['unit']}) ---")
            email_body_text += f"Location: {loc['address']} #{loc['unit']}\n"
            
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            try:
                print(f"Navigating to {TARGET_URL}...")
                # Using domcontentloaded to prevent cloud timeouts
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)

                # Step 1: Type Address
                print(f"Targeting visible address input and typing {loc['address']}...")
                address_input = page.get_by_placeholder("Enter your address").locator("visible=true").first
                address_input.click(force=True)
                page.wait_for_timeout(1000)
                
                address_main = loc['address'][:-1]
                address_last = loc['address'][-1]
                
                address_input.press_sequentially(address_main, delay=150)
                page.wait_for_timeout(2000)
                address_input.press_sequentially(address_last, delay=200)
                page.wait_for_timeout(4000)

                # Step 2: Select Google Places Item
                print("Clicking the Google Places dropdown...")
                pac_item = page.locator(".pac-container .pac-item").first
                if pac_item.is_visible(timeout=5000):
                    pac_item.click(force=True)
                else:
                    address_input.press("ArrowDown")
                    page.wait_for_timeout(1000)
                    address_input.press("Enter")
                
                page.wait_for_timeout(4000)

                # Step 3: Select Unit
                print(f"Clicking Unit field and selecting {loc['unit']}...")
                unit_field = page.locator("input[placeholder*='Unit' i], select[name*='unit' i], input[name*='unit' i]").locator("visible=true").first
                if unit_field.is_visible(timeout=5000):
                    unit_field.click(force=True)
                    page.wait_for_timeout(1000)
                    
                    if unit_field.evaluate("el => el.tagName.toLowerCase() === 'select'"):
                        try:
                            unit_field.select_option(label=loc['unit'])
                        except:
                            unit_field.select_option(value=loc['unit'])
                    else:
                        unit_field.press_sequentially(loc['unit'], delay=200)
                        page.wait_for_timeout(1500)
                        page.keyboard.press("ArrowDown")
                        page.wait_for_timeout(500)
                        page.keyboard.press("Enter")

                page.wait_for_timeout(3000)

                # Step 4: Click Check Availability
                print("Clicking 'Check availability'...")
                check_button = page.locator("button:has-text('Check availability'), button:has-text('Check Availability')").locator("visible=true").first
                if check_button.is_visible(timeout=5000):
                    check_button.click(force=True)
                else:
                    page.keyboard.press("Enter")
                
                page.wait_for_timeout(8000)

                # Step 5: Click through intermediary screens
                print("Clicking through intermediary screens...")
                for i in range(5):
                    next_btn = page.locator("button:has-text('Next'), button:has-text('Continue'), button:has-text('Confirm'), button:has-text('Verify')").locator("visible=true").first
                    if next_btn.is_visible(timeout=5000):
                        print(f"Clicking intermediary button (Screen {i+1})...")
                        next_btn.click(force=True)
                        page.wait_for_timeout(6000)
                    
                    calendar_check = page.locator("text='Select a date and time', [role='tab']")
                    if calendar_check.count() > 0 and calendar_check.first.is_visible():
                        print("Successfully reached the appointment calendar!")
                        break

                page.wait_for_timeout(5000) 

                # Step 6: Capture 3 distinct available days
                print("Capturing 3 available days...")
                loc_screenshots_taken = 0
                for i in range(1, 7): 
                    if loc_screenshots_taken >= 3:
                        break
                        
                    target_date = datetime.now() + timedelta(days=i)
                    day_num_str = target_date.strftime('%d').lstrip('0')
                    day_name = target_date.strftime('%A')
                    date_label = target_date.strftime('%A, %B %d, %Y')
                    
                    print(f"Checking {day_name} (Date: {day_num_str})...")
                    day_card = page.get_by_text(day_num_str, exact=True).locator("visible=true").first
                    
                    if not day_card.is_visible(timeout=2000):
                        next_arrow = page.locator("button[aria-label*='next' i], button:has-text('>')").locator("visible=true").first
                        if next_arrow.is_visible():
                            next_arrow.click(force=True)
                            page.wait_for_timeout(1500)
                    
                    if day_card.is_visible():
                        day_card.click(force=True)
                        page.wait_for_timeout(1500)
                        
                        is_disabled = day_card.evaluate("el => el.disabled || el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true' || el.className.includes('disabled') || el.className.includes('unavailable') || el.style.color === 'rgb(204, 204, 204)'")
                        
                        if is_disabled:
                            print(f"--> {day_name} is disabled. Skipping.")
                            continue
                        
                        print(f"--> Waiting 6 seconds for {day_name} slots to load...")
                        page.wait_for_timeout(6000)
                        
                        filename = f"{loc['prefix']}_schedule_{day_num_str}.png"
                        page.screenshot(path=filename, full_page=True)
                        captured_screenshots.append((f"{loc['label']} - {date_label}", filename))
                        loc_screenshots_taken += 1

            except Exception as e:
                print(f"Error processing {loc['label']}: {e}")
                traceback.print_exc()
                try:
                    fallback_name = f"{loc['prefix']}_fallback.png"
                    page.screenshot(path=fallback_name, timeout=5000)
                    captured_screenshots.append((f"{loc['label']} - Error State", fallback_name))
                    email_body_text += f"[ERROR] Failed to fetch schedule for {loc['label']}. See attached debug screenshot.\n"
                except Exception as fallback_err:
                    print(f"Fallback screenshot failed: {fallback_err}")

            finally:
                context.close()
                email_body_text += "\n"

        browser.close()

    if not captured_screenshots:
        email_body_text += "[WARNING]: No screenshots were captured for any location. The site may be blocking access or loading too slowly.\n"

    email_body_text += f"Target URL: {TARGET_URL}\n\nAttached are the installation schedule screenshots."
    send_email_with_multiple_attachments("GFiber Webpass Schedule: SF & Seattle", email_body_text, captured_screenshots)

def send_email_with_multiple_attachments(subject, body, screenshots):
    sender_email = os.environ.get("SENDER_EMAIL", DEFAULT_SENDER).strip()
    sender_password = os.environ.get("SENDER_PASSWORD", "").replace(" ", "").strip()
    recipient_email_str = os.environ.get("RECIPIENT_EMAIL", DEFAULT_RECIPIENTS)
    recipients = [r.strip() for r in recipient_email_str.split(",") if r.strip()]

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain"))

    for date_label, shot_path in screenshots:
        if os.path.exists(shot_path):
            try:
                with open(shot_path, "rb") as f:
                    img = MIMEImage(f.read(), name=os.path.basename(shot_path))
                    img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(shot_path))
                    msg.attach(img)
            except:
                pass

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
    except Exception:
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipients, msg.as_string())
        except Exception as err:
            raise err

if __name__ == "__main__":
    run_agent()
