try:
    import budoux
except ImportError:
    LOGGER.warning("缺少依赖包budoux, 请更新依赖")

from GalTransl import LOGGER
from GalTransl.CSentense import CSentense
from GalTransl.GTPlugin import GTextPlugin

class LineBreakFix(GTextPlugin):
    def gtp_init(self, plugin_conf: dict, project_conf: dict):
        """
        初始化插件
        :param plugin_conf: 插件配置字典
        :param project_conf: 项目配置字典
        """
        # 从配置中获取插件名称，默认为"行内换行修复"
        self.pname = plugin_conf["Core"].get("Name", "行内换行修复")
        settings = plugin_conf["Settings"]
        LOGGER.info(f"[{self.pname}] 插件启动")

        # 从配置中读取设置
        self.linebreak = settings.get("换行符", "[r]")  # 换行符，默认为"[r]"
        self.mode = settings.get("换行模式", "保持位置")  # 换行模式，默认为"保持位置"
        self.force_fix = settings.get("强制修复", False)  # 是否强制修复，默认为False

        # 输出设置信息
        LOGGER.info(f"[{self.pname}] 换行符: {self.linebreak}")
        LOGGER.info(f"[{self.pname}] 换行模式: {self.mode}")
        LOGGER.info(f"[{self.pname}] 强制修复: {self.force_fix}")

        # 初始化BudouX解析器（简体中文）
        self.parser = budoux.load_default_simplified_chinese_parser()

    def after_dst_processed(self, tran: CSentense) -> CSentense:
        """
        在目标文本处理之后的操作，主要的换行符修复逻辑
        :param tran: CSentense对象
        :return: 处理后的CSentense对象
        """
        src_breaks = tran.pre_jp.count(self.linebreak)
        dst_breaks = tran.post_zh.count(self.linebreak)
        LOGGER.debug(f"[{self.pname}] 源文本换行符数量: {src_breaks}")
        LOGGER.debug(f"[{self.pname}] 目标文本换行符数量: {dst_breaks}")

        if src_breaks == dst_breaks and not self.force_fix:
            return tran

        LOGGER.info(f"[{self.pname}] {'强制修复' if self.force_fix else '发现源文本和目标文本的换行符数量不一致'}，正在进行换行符修复，模式: {self.mode}")

        # 根据不同的换行模式调用相应的处理方法
        if self.mode == "平均":
            tran.post_zh = self.average_mode(tran.post_zh, src_breaks)
        elif self.mode == "切最长":
            tran.post_zh = self.intersperse_mode(tran.post_zh, src_breaks)
        elif self.mode == "保持位置":
            tran.post_zh = self.keep_position_mode(tran.post_zh, tran.post_jp, src_breaks)
        else:
            LOGGER.warning(f"[{self.pname}] 未知的换行模式: {self.mode}")

        return tran

    def average_mode(self, text: str, target_breaks: int) -> str:
        """
        平均模式：忽略原有换行符，将文本等分，在等分点插入换行符
        :param text: 原文本
        :param target_breaks: 目标换行符数量
        :return: 处理后的文本
        """
        text_without_breaks = text.replace(self.linebreak, '')
        total_length = len(text_without_breaks)
        chars_per_slice = total_length // (target_breaks + 1)
        
        phrases = self.parser.parse(text_without_breaks)
        result = []
        current_length = 0
        breaks_added = 0
        
        for phrase in phrases:
            result.append(phrase)
            current_length += len(phrase)
            if current_length >= chars_per_slice and breaks_added < target_breaks:
                result.append(self.linebreak)
                current_length = 0
                breaks_added += 1
        
        # 如果还没有添加足够的换行符，在最后添加
        while breaks_added < target_breaks:
            result.append(self.linebreak)
            breaks_added += 1
        
        return ''.join(result)

    def intersperse_mode(self, text: str, target_breaks: int) -> str:
        """
        切最长模式：保留原有换行符，反复找最长片段从中间切分，直到达到目标换行符数量
        :param text: 原文本
        :param target_breaks: 目标换行符数量
        :return: 处理后的文本
        """
        slices = text.split(self.linebreak)
        while len(slices) - 1 < target_breaks:
            longest_slice_index = max(range(len(slices)), key=lambda i: len(slices[i]))
            longest_slice = slices[longest_slice_index]
            phrases = self.parser.parse(longest_slice)
            
            if len(phrases) < 2:
                # 如果无法再分割，就在最后添加空字符串
                slices.append('')
            else:
                mid = len(phrases) // 2
                left_part = ''.join(phrases[:mid])
                right_part = ''.join(phrases[mid:])
                slices[longest_slice_index:longest_slice_index+1] = [left_part, right_part]
        
        return self.linebreak.join(slices[:target_breaks+1])

    def keep_position_mode(self, text: str, src_text: str, target_breaks: int) -> str:
        """
        保持位置模式：忽略原有换行符，根据原文的换行符相对位置，重新计算目标换行符的位置，保证相对位置不变
        :param text: 目标文本
        :param src_text: 源文本
        :param target_breaks: 目标换行符数量
        :return: 处理后的文本
        """
        src_length = len(src_text.replace(self.linebreak, ''))
        dst_length = len(text.replace(self.linebreak, ''))
        
        src_breaks = src_text.split(self.linebreak)
        break_positions = []
        current_length = 0
        
        for i, slice in enumerate(src_breaks):
            if i < len(src_breaks) - 1:  # 不计算最后一个换行符后的位置
                current_length += len(slice)
                break_positions.append(int(current_length / src_length * dst_length))
        
        phrases = self.parser.parse(text.replace(self.linebreak, ''))
        result = []
        current_length = 0
        break_index = 0
        
        for phrase in phrases:
            result.append(phrase)
            current_length += len(phrase)
            if break_index < len(break_positions) and current_length >= break_positions[break_index]:
                result.append(self.linebreak)
                break_index += 1
        
        # 如果还没有添加足够的换行符，在最后添加
        while break_index < target_breaks:
            result.append(self.linebreak)
            break_index += 1
        
        return ''.join(result)

    def gtp_final(self):
        """
        插件结束时的操作
        """
        pass