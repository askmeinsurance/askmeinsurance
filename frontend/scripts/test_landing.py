from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto("http://localhost:5173")
    page.wait_for_load_state("networkidle")

    print("=== Landing Page Tests ===\n")

    # Screenshot
    page.screenshot(path="/tmp/landing_before.png", full_page=True)
    print("Screenshot saved: /tmp/landing_before.png")

    # 1. Sidebar presence
    sidebar = page.locator("text=InsureBot SG")
    print(f"[{'PASS' if sidebar.count() > 0 else 'FAIL'}] Sidebar brand name visible")

    new_chat = page.locator("text=New chat")
    print(f"[{'PASS' if new_chat.count() > 0 else 'FAIL'}] 'New chat' button present")

    # 2. Greeting
    greeting = page.locator("text=Where should we start?")
    print(f"[{'PASS' if greeting.count() > 0 else 'FAIL'}] Greeting text visible")

    # 3. Chat input
    chat_input = page.locator("textarea, input[placeholder]")
    print(f"[{'PASS' if chat_input.count() > 0 else 'FAIL'}] Chat input present")

    # 4. Suggestion chips
    chips = ["Create image", "Create music", "Help me learn", "Write anything", "Boost my day", "Create a video"]
    for chip in chips:
        el = page.locator(f"text={chip}")
        print(f"[{'PASS' if el.count() > 0 else 'FAIL'}] Chip '{chip}' present")

    # 5. Check centering: main content area bounding box
    main_area = page.locator("main, [class*='flex-1']").first
    if main_area.count() > 0:
        box = main_area.bounding_box()
        print(f"\n[INFO] Main area: x={box['x']:.0f}, width={box['width']:.0f}")

    greeting_el = page.locator("text=Where should we start?")
    if greeting_el.count() > 0:
        gbox = greeting_el.bounding_box()
        vp_width = page.viewport_size["width"]
        sidebar_width = 260  # from Sidebar.tsx: style={{ width: '260px' }}
        content_area_width = vp_width - sidebar_width
        content_center = sidebar_width + content_area_width / 2
        element_center = gbox["x"] + gbox["width"] / 2
        offset = abs(element_center - content_center)
        print(f"[INFO] Viewport width: {vp_width}, Content area center: {content_center:.0f}")
        print(f"[INFO] Greeting element center: {element_center:.0f}, Offset from center: {offset:.0f}px")
        print(f"[{'PASS' if offset < 50 else 'FAIL'}] Chat panel is centered (offset: {offset:.0f}px)")

    # 6. Sidebar chat history
    history_items = ["Understanding life insurance", "Term vs whole life policy", "Critical illness coverage", "Medishield Life top-ups"]
    for item in history_items:
        el = page.locator(f"text={item}")
        print(f"[{'PASS' if el.count() > 0 else 'FAIL'}] History item '{item}' present")

    # 7. Bottom nav
    settings = page.locator("text=Settings")
    help_btn = page.locator("text=Help")
    print(f"[{'PASS' if settings.count() > 0 else 'FAIL'}] Settings link present")
    print(f"[{'PASS' if help_btn.count() > 0 else 'FAIL'}] Help link present")

    browser.close()
    print("\nDone.")
