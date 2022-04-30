# -*- coding: utf-8 -*-
import random
from gc import collect
from time import sleep, localtime, strftime

import win32com.client
from win32gui import GetWindowText, GetWindowRect, GetForegroundWindow, SetForegroundWindow
from modules.ModuleGetTargetInfo import GetTargetPicInfo
from modules.ModuleGetScreenCapture import GetScreenCapture
from modules.ModuleHandleSet import HandleSet
from modules.ModuleImgProcess import ImgProcess
from modules.ModuleGetPos import GetPosByTemplateMatch, GetPosBySiftMatch
from modules.ModuleDoClick import DoClick


def time_transform(seconds):
    """
    转换时间格式 秒—>时分秒
    :param seconds: 秒数
    :return: 时分秒格式
    """
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    run_time = "%02d时%02d分%02d秒" % (h, m, s)
    return run_time


def get_active_window(loop_times=5):
    """
    点击鼠标获取目标窗口句柄
    :param loop_times: 倒计时/循环次数
    :return: 窗体标题名称
    """
    hand_num = ""
    hand_win_title = ""
    for t in range(loop_times):
        print(f'请在倒计时 [ {loop_times} ] 秒结束前，点击目标窗口')
        loop_times -= 1
        hand_num = GetForegroundWindow()
        hand_win_title = GetWindowText(hand_num)
        print(f"目标窗口： [ {hand_win_title} ] [ {hand_num} ] ")
        sleep(1)  # 每1s输出一次
    left, top, right, bottom = GetWindowRect(hand_num)
    print("-----------------------------------------------------------")
    print(f"目标窗口: [ {hand_win_title} ] 窗口大小：[ {right - left} X {bottom - top} ]")
    print("-----------------------------------------------------------")
    return hand_win_title, hand_num


class StartMatch:

    def __init__(self, gui_info):
        super(StartMatch, self).__init__()
        self.connect_mod, self.target_modname, self.hwd_title, self.click_deviation, self.interval_seconds, self.loop_min, self.compress_val, self.match_method, self.scr_and_click_method, self.custom_target_path, self.process_num, self.handle_num = gui_info

    def set_init(self):
        """
        获取待匹配的目标图片信息、计算循环次数、时间、截图方法
        :return: 循环次数、截图方法、图片信息、每次循环大约需要执行的时间
        """
        # 参数初始化
        target_modname = self.target_modname
        custom_target_path = self.custom_target_path
        connect_mod = self.connect_mod
        interval_seconds = self.interval_seconds
        loop_min = self.loop_min
        scr_and_click_method = self.scr_and_click_method
        handle_num = str(self.handle_num).split(",")
        # 获取待检测目标图片信息
        print('目标图片读取中……')
        target_info = GetTargetPicInfo(target_modname, custom_target_path,
                                       compress_val=1).get_target_info  # 目标图片不压缩（本身就小）
        target_img_sift, target_img_hw, target_img_name, target_img_file_path, target_img = target_info
        print(f'读取完成！共[ {len(target_img)} ]张图片\n{target_img_name}')

        # 计算循环次数、时间
        t1 = len(target_img) / 30  # 每次循环匹配找图需要消耗的时间, 脚本每次匹配一般平均需要2.5秒（30个匹配目标）
        loop_min = int(loop_min)  # 初始化执行时间，因为不能使用字符串，所以要转一下
        interval_seconds = int(interval_seconds)  # 初始化间隔秒数
        loop_times = int(loop_min * (60 / (interval_seconds + t1)))  # 计算要一共要执行的次数

        # 句柄操作（获取句柄编号、设置优先级、检测程序是否运行）
        screen_method = GetScreenCapture()
        if connect_mod == 'Windows程序窗体':
            if len(handle_num) == 1:  # 如果只获取到一个窗口句柄
                handle_num = int(handle_num[0])
                handle_set = HandleSet(self.hwd_title, handle_num)
                handle_num = handle_set.get_handle_num
                handle_width = handle_set.get_handle_pos[2] - handle_set.get_handle_pos[0]  # 右x - 左x 计算宽度
                handle_height = handle_set.get_handle_pos[3] - handle_set.get_handle_pos[1]  # 下y - 上y 计算高度
                # 设置目标程序优先级，避免程序闪退（痒痒鼠在我电脑总是闪退，设置优先级后就不闪退了），若需要可以打开，脚本打包成exe可执行程序运行时，会报错，不知道什么原因
                # self.handle_set.set_priority(4)
                screen_method = GetScreenCapture(handle_num, handle_width, handle_height)

                # 通过pywin32模块下的SetForegroundWindow函数调用时，会出现
                # error: (0, 'SetForegroundWindow', 'No error message is available')报错，为pywin32模块下的一个小bug，
                # 在该函数调用前，需要先发送一个其他键给屏幕
                if scr_and_click_method == '兼容模式':
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shell.SendKeys('%')
                    SetForegroundWindow(handle_num)  # 窗口置顶
                    sleep(0.2)
            else:
                print("暂不支持一次选择多个窗口！")
                return False

        # 检测安卓设备是否正常连接
        elif connect_mod == 'Android-Adb':
            adb_device_connect_status, device_id = HandleSet.adb_device_status()
            if adb_device_connect_status:
                print(f'已连接设备[ {device_id} ]')
            else:
                print(device_id)
                return False
        return loop_times, screen_method, target_info, t1

    def start_match_click(self, i, loop_times, screen_method, target_info, debug_status):
        match_status = False
        run_status = True
        connect_mod = self.connect_mod
        scr_and_click_method = self.scr_and_click_method
        match_method = self.match_method
        compress_val = float(self.compress_val)
        click_deviation = int(self.click_deviation)
        target_img_sift, target_img_hw, target_img_name, target_img_file_path, target_img = target_info

        # 计算进度
        now_time = strftime("%Y-%m-%d %H:%M:%S", localtime())
        progress = format((i + 1) / loop_times, '.2%')
        print(f"第 [ {i + 1} ] 次匹配, 还剩 [ {loop_times - i - 1} ] 次 \n当前进度 [ {progress} ] \n当前时间 [ {now_time} ]")

        # 获取截图
        print('正在截图…')
        screen_img = None
        if connect_mod == 'Windows程序窗体':
            handle_set = HandleSet(self.hwd_title, self.handle_num)
            if not handle_set.handle_is_active():
                run_status = False
                return run_status, match_status
            # 如果部分窗口不能点击、截图出来是黑屏，可以使用兼容模式
            if scr_and_click_method == '正常-可后台':
                screen_img = screen_method.window_screen()
            elif scr_and_click_method == '兼容-不可后台':
                screen_img = screen_method.window_screen_bk()

        # 支持安卓adb连接
        elif connect_mod == 'Android-手机':
            adb_device_connect_status, device_id = HandleSet.adb_device_status()
            if adb_device_connect_status:
                screen_img = screen_method.adb_screen()
            else:
                print(device_id)
                run_status = False
                return run_status, match_status

        if debug_status:
            ImgProcess.show_img(screen_img)  # test显示截图

        # 开始匹配
        print("正在匹配…")
        pos = None
        target_num = None
        target_img_tm = target_img

        # 模板匹配方法
        if match_method == '模板匹配':
            if compress_val != 1:  # 压缩图片，模板和截图必须一起压缩
                screen_img = ImgProcess.img_compress(screen_img, compress_val)
                if debug_status:
                    ImgProcess.show_img(screen_img)  # test显示压缩后截图
                target_img_tm = []
                for k in range(len(target_img)):
                    target_img_tm.append(ImgProcess.img_compress(target_img[k], compress_val))

            # 开始匹配
            get_pos = GetPosByTemplateMatch()
            pos, target_num = get_pos.get_pos_by_template(screen_img, target_img_tm, debug_status)

        # 特征点匹配方法，准确度不能保证，但是不用适配不同设备
        elif match_method == '特征点匹配':
            if compress_val != 1:  # 压缩图片，特征点匹配方法，只压缩截图
                screen_img = ImgProcess.img_compress(screen_img, compress_val)
                if debug_status:
                    ImgProcess.show_img(screen_img)  # test显示压缩后截图
            screen_sift = ImgProcess.get_sift(screen_img)  # 获取截图的特征点

            # 开始匹配
            get_pos = GetPosBySiftMatch()
            pos, target_num = get_pos.get_pos_by_sift(target_img_sift, screen_sift,
                                                      target_img_hw,
                                                      target_img, screen_img, debug_status)
            del screen_sift  # 删除截图的特征点信息

        if pos and target_num is not None:
            match_status = True

            # 如果图片有压缩，需对坐标还原
            if compress_val != 1:
                pos = [pos[0] / compress_val, pos[1] / compress_val]

            # 打印匹配到的实际坐标点和匹配到的图片信息
            print(f"匹配成功! 匹配到第 [ {target_num + 1} ] 张图片: [ {target_img_name[target_num]} ]\n"
                  f"坐标位置: [ {int(pos[0])} , {int(pos[1])} ] ")

            # 开始点击
            if connect_mod == 'Windows程序窗体':
                handle_set = HandleSet(self.hwd_title, self.handle_num)
                handle_set.handle_is_active()
                handle_num = handle_set.get_handle_num
                doclick = DoClick(pos, click_deviation, handle_num)

                # 如果部分窗口不能点击、截图出来是黑屏，可以使用兼容模式
                if scr_and_click_method == '正常-可后台':
                    doclick.windows_click()
                elif scr_and_click_method == '兼容-不可后台':
                    doclick.windows_click_bk()

            # 支持安卓adb连接
            elif connect_mod == 'Android-手机':
                doclick = DoClick(pos, click_deviation)
                doclick.adb_click()
        else:
            print("匹配失败！")
            match_status = False

        # 内存清理
        del screen_img, pos, target_info, target_img, target_img_sift, screen_method  # 删除变量
        collect()  # 清理内存
        return run_status, match_status

    def simulates_real_clicks(self):
        """模拟真实点击：屏幕随机点击多次"""

        if self.connect_mod == 'Windows程序窗体':
            handle_set = HandleSet(self.hwd_title, self.handle_num)
            handle_width = handle_set.get_handle_pos[2] - handle_set.get_handle_pos[0]  # 右x - 左x 计算宽度
            handle_height = handle_set.get_handle_pos[3] - handle_set.get_handle_pos[1]  # 下y - 上y 计算高度
            pos = [int(handle_width / 2), int(handle_height / 2)]
            real_clicks = DoClick(pos, 200, handle_set.get_handle_num)
            if self.scr_and_click_method == '正常-可后台':
                real_clicks.windows_click()
            elif self.scr_and_click_method == '兼容-不可后台':
                real_clicks.windows_click_bk()

        elif self.connect_mod == 'Android-手机':
            pos = [random.randint(400, 500), random.randint(400, 500)]
            real_clicks = DoClick(pos, 200)
            real_clicks.adb_click()
        yc = random.uniform(0.2, 0.8)
        # print(f'{round(yc,2)}秒后继续')
        sleep(yc)  # 延迟

    @staticmethod
    def time_warming():
        """检测时间是否晚12-早8点之间，这个时间可能因为异常导致封号"""

        if localtime().tm_hour < 8:
            now_time = strftime("%H:%M:%S", localtime())
            print("----------------------------------------------------------")
            print(f"现在 [ {now_time} ]【非正常游戏时间，请谨慎使用】")
            print("----------------------------------------------------------")
            for t in range(8):
                print(f"[ {8 - t} ] 秒后开始……")
                sleep(1)
            print("----------------------------------------------------------")