from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    # 登录  由于系统登录有效期较短，所有的新增、查询、删除操作都需要重新走一遍登录流程
    page.goto("https://10.177.172.216:28443/login")
    page.get_by_placeholder("用户名/手机号/邮箱").click()
    page.get_by_placeholder("用户名/手机号/邮箱").fill("")
    page.get_by_role("button", name="下一步").click()
    page.get_by_placeholder("请输入密码").click()
    page.get_by_placeholder("请输入密码").fill("")
    page.get_by_role("button", name="立即登录").click()
    # 点击弹窗
    page.get_by_role("button", name="确 认").click()
    page.get_by_role("button", name="我知道了").click()
    # 进入目标页面
    page.get_by_text("资产管理", exact=True).click()
    page.get_by_role("link", name="终端任务").click()

    # 新建即时消息通知
    page.get_by_role("button", name="新建").click()
    page.get_by_placeholder("请输入").click()
    # 输入即时消息任务名称，需要保证改名称不重复并体现出来源
    page.get_by_placeholder("请输入").fill("test")
    page.get_by_placeholder("请选择任务类型").click()
    page.get_by_title("即时消息").click()
    page.get_by_placeholder("请输入消息标题").click()
    # 标题为通知标题 参考邮件
    page.get_by_placeholder("请输入消息标题").fill("test title")
    page.locator(".ql-editor").click()
    # 通知正文，展示所有任务信息 参考邮件。但由于即时通知无法交互，所以不用展示回复指引，提示用户通过邮件回复
    page.locator(".ql-editor").fill("test content")
    page.get_by_placeholder("请输入发布人").click()
    # 发布人 为任务创建人
    page.get_by_placeholder("请输入发布人").fill("test 发布人")
    page.get_by_role("button", name="下一步").click()
    page.get_by_role("textbox", name="请选择").click()
    page.get_by_title("普通分组").click()
    page.get_by_text("请选择").click()
    page.locator(".checkbox-btn").first.click()
    page.get_by_role("button", name="确 认").click()
    page.get_by_role("radio", name="所选分组的部分终端").click()
    page.get_by_role("radio", name="终端列表").click()
    page.get_by_role("button", name="添 加").click()
    page.get_by_role("textbox", name="终端名称/IP地址/使用人").click()
    # ip为通知目标的ip
    page.get_by_role("textbox", name="终端名称/IP地址/使用人").fill("24.62.6.79")
    page.get_by_role("textbox", name="终端名称/IP地址/使用人").press("Enter")
    page.locator(".cell > .q-checkbox > .q-checkbox__input > .q-checkbox__inner").first.click()
    page.get_by_role("button", name="确 定").click()
    page.get_by_role("button", name="下一步").click()
    page.get_by_role("button", name="下一步").click()
    page.get_by_role("button", name="确 认").click()

    # 匹配即时消息任务名称 -若当前任务在任务协同系统中通知模块中状态已经更新为已读，则删除该任务
    page.locator(".q-table_11_column_68 > .cell").first.click()
    page.locator("[id=\"__qiankun_microapp_wrapper_for_management__\"]").get_by_text("getcodegen").click()
    page.get_by_label("Breadcrumb").get_by_text("终端任务").click()
    page.locator(".q-table__fixed-body-wrapper > .q-table__body > tbody > tr:nth-child(6) > .q-table_15_column_86 > .cell > .checkbox > .q-checkbox > .q-checkbox__input > .q-checkbox__inner").click()
    page.get_by_role("button", name="删除").click()
    page.get_by_role("button", name="确 认").click()

    # 定时匹配即时消息任务名称，查看即时消息执行状态，并回写到任务协同系统中通知模块
    with page.expect_popup() as page1_info:
        page.get_by_role("row", name="getcodegen 基础功能- 即时消息 执行一次 执行中 宋辉 2026-04-28 17:12:47 查看子任务 查看结果 更多 ").get_by_role("button").nth(1).click()
    page1 = page1_info.value
    page1.get_by_role("button", name="Close").click()
    page1.locator(".q-table__fixed-body-wrapper > .q-table__body > tbody > .q-table__row > .q-table_3_column_11 > .cell > .checkbox > .q-checkbox > .q-checkbox__input > .q-checkbox__inner").click()
    page1.get_by_text("正在执行").click()
    page1.get_by_text("执行状态").first.click()
    page1.get_by_role("cell", name="正在执行").locator("div").first.click(button="right")
    page1.locator(".biz-skylar-pagination-table > div > .q-table > .q-table__body-wrapper").click()
    page1.locator(".q-table__fixed-body-wrapper > .q-table__body > tbody > .q-table__row > .q-table_3_column_11 > .cell > .checkbox > .q-checkbox > .q-checkbox__input > .q-checkbox__inner").click()
    page1.get_by_text("执行状态").first.click()
    with page.expect_popup() as page2_info:
        page.get_by_role("row", name="bdk0001 基础功能- 更新客户端 执行一次 执行结束 admin 2026-04-23 10:48:42 查看子任务 查看结果 更多 ").get_by_role("button").nth(1).click()
    page2 = page2_info.value
    page2.get_by_role("button", name="Close").click()
    page2.get_by_role("cell", name="已过期").click()
    page2.get_by_role("cell", name="24.62.7.3").click()
    page2.get_by_role("cell", name="IP地址").first.click()
    page2.get_by_text("2", exact=True).click()
    page2.get_by_text("1", exact=True).click()
    page2.locator(".q-table_3_column_18 > .cell > .render-slot").first.click()
    page2.locator("td:nth-child(8)").first.click()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
