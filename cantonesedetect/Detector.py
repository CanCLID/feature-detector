"""
Core logic:
1. If quote is true, judge the input into 6 labels, otherwise 4 labels.
2. If split_seg is true, judge the input by aggregating the judgements of the segments. Otherwise judge the input as a whole segment.
3. If print_stat is true, print the Cantonese and SWC ratio to I/O. 
"""
import math
import re
from collections import Counter
from typing import Tuple

from cantonesedetect.SegmentFeatures import SegmentFeatures

# Cantonese characters not found in SWC
CANTO_FEATURE_RE = re.compile(
    r'[嘅嗰啲咗佢喺咁噉冇啩哋畀嚟諗惗乜嘢閪撚𨳍𨳊瞓睇㗎餸𨋢摷喎嚿噃嚡嘥嗮啱揾搵喐逳噏𢳂岋糴揈捹撳㩒𥄫攰癐冚孻冧𡃁嚫跣𨃩瀡氹嬲掟孭黐唞㪗埞忟𢛴嗱係唔喇俾]|'
    r'唔[係得會好識使洗駛通知到去走掂該錯差]|點[樣會做得解]|[琴尋噚聽第]日|[而依]家|家[下陣]|[真就實梗又話都]係|邊[度個位科]|'
    r'[嚇凍攝整揩逢淥浸激][親嚫]|[橫搞傾諗得唔]掂|仲[有係話要得好衰唔]|返[學工去歸]|執[好生實返輸]|[留坐剩]低|'
    r'屋企|收皮|慳錢|傾[偈計]|幫襯|求其|是[但旦]|[濕溼]碎|零舍|肉[赤緊酸]|核突|同埋|勁[秋抽]|邊[度隻條張樣個]|去邊'
)

# A list of exceptions where the above characters can be found in SWC
CANTO_EXCLUDE_RE = re.compile(r'(關係|吱唔|咿唔|喇嘛|喇叭|俾路支|俾斯麥)')

# SWC characters that are less common in Cantonese
SWC_FEATURE_RE = re.compile(r'[這哪唄咱啥甭那是的他她它吧沒麼么些了卻説說吃弄把也在]|而已')

# A list of exceptions where the above characters can be found in Cantonese (mainly phrases or proper nouns)
SWC_EXCLUDE_RE = re.compile(
    r'亞利桑那|剎那|巴塞羅那|薩那|沙那|哈瓦那|印第安那|那不勒斯|支那|'
    r'是[否日次非但旦]|[利於]是|唯命是從|頭頭是道|似是而非|自以為是|俯拾皆是|撩是鬥非|莫衷一是|唯才是用|'
    r'[目綠藍紅中]的|的[士確式]|波羅的海|眾矢之的|的而且確|大眼的度|的起心肝'
    r'些[微少許小]|'
    r'[淹沉浸覆湮埋沒出]沒|沒[落頂收]|神出鬼沒|'
    r'了[結無斷當然哥結得解事之]|[未明]了|不得了|大不了|'
    r'他[信人國日殺鄉]|[其利無排維結]他|馬耳他|他加祿|他山之石|'
    r'其[它]|'
    r'[酒網水貼]吧|吧[台臺枱檯]|'
    r'[退忘阻]卻|卻步|'
    r'[遊游小傳解學假淺眾衆訴論][説說]|[說説][話服明]|自圓其[説說]|長話短[說説]|不由分[說説]|'
    r'吃[虧苦力]|'
    r'弄[堂]'
    r'把[握柄持火風關鬼口嘴戲脈炮砲屁手聲]|大把|拉把|冧把|掃把|拖把|得把|加把|下把位|一把年紀|把死人聲|自把自為|兩把|三把|四把|五把|幾把|拎把|第一把|泵把|'
    r'也[許門]|[非威]也|也文也武|之乎者也|維也納|空空如也|頭也不回|時也[命運]也|'
    r'在[場乎下校學行任野意於望內案旁生世心線逃位即職座囚此家]|[站志旨爭所勝衰實內外念現好健存潛差弊活]在|我思故我在'
)

# A list of quotes: Content inside and outside a pair of quotes should be treated separately.
ALL_QUOTEMARKS_RE = re.compile(
    r'「([^「]*)」|“([^“]*)”|《([^《]*)》|【([^【]*)】|『([^『]*)』')

# A list of sentential delimiters
ALL_DELIMITERS_RE = re.compile(r'[，。；？！⋯\n]')

ALL_HAN_RE = re.compile(
    r'[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002a6df\U0002a700-\U0002ebef'
    r'\U00030000-\U000323af\ufa0e\ufa0f\ufa11\ufa13\ufa14\ufa1f\ufa21\ufa23\ufa24\ufa27\ufa28\ufa29\u3006\u3007]'
    r'[\ufe00-\ufe0f\U000e0100-\U000e01ef]?')


class CantoneseDetector:
    """
    To judge a document, you can either judge the entire document with as one single segment based on its Cantonese and SWC presence,
    or split the document into segments and aggregate the judgement from the segments.

    Attributes:
        split_seg (bool): Split the document into segments if True. Defaults to False.
        get_quote (bool): Separate Matrix and Quote if True. Defaults to False.
        print_stat (bool): Print judgement to I/O if True. Defaults to False.
    """

    def __init__(self, split_seg: bool = False, get_quote: bool = False, print_stat: bool = False, canto_tolerance: float = 0.01, swc_tolerance: float = 0.01, canto_presence: float = 0.03, swc_presence: float = 0.03) -> None:
        """
        Initialize the thresholds
        """
        # If True, split the document into segments, and the final judgement is aggregated from the segments.
        self.split_seg: bool = split_seg
        # If True, separate Matrix and Quote, and the final judgement is aggregated from the two parts.
        self.get_quote: bool = get_quote
        self.print_stat: bool = print_stat

        # Cantonese features in less than 1% of the text will still be considered SWC.
        self.canto_tolerance: float = canto_tolerance
        # SWC features in less than 1% of the text will still be considered Written Cantonese.
        self.swc_tolerance: float = swc_tolerance
        # The minimum Cantonese features expected to be found in Mixed or Cantonese text.
        self.canto_presence: float = canto_presence
        # The minimum SWC features expected to be found in Mixed or SWC text.
        self.swc_presence: float = swc_presence

    def _hant_length(self, segment: str) -> int:
        """
        Return the number of Han characters in a segment.

        Args:
            segment (str): The segment of text to be analyzed.

        Returns:
            int: The number of Han characters in the segment.
        """
        return sum(1 for _ in ALL_HAN_RE.finditer(segment))

    def _separate_quotes(self, document: str) -> Tuple[str, str]:
        """
        Extract quotes and matrix from a document.

        Args:
            document (str): The input document from which quotes and matrix will be extracted.

        Returns:
            quotes (Tuple[str, str]): A tuple containing the matrix and quotes extracted from the document.
        """
        matrix = re.sub(ALL_QUOTEMARKS_RE, "…", document)
        quote_segments = re.findall(ALL_QUOTEMARKS_RE, document)
        quotes = "…".join(["".join(s) for s in quote_segments])

        return matrix, quotes

    def _get_segment_features(self, segment: str) -> SegmentFeatures:
        """
        Extract and set Cantonese and SWC features in a segment.

        Args:
            segment (str): The segment of text to be analyzed.

        Returns:
            None
        """
        canto_feature = CANTO_FEATURE_RE.findall(segment)
        canto_exclude = CANTO_EXCLUDE_RE.findall(segment)
        swc_feature = SWC_FEATURE_RE.findall(segment)
        swc_exclude = SWC_EXCLUDE_RE.findall(segment)

        canto_feature_count: int = len(canto_feature) - len(canto_exclude)
        swc_feature_count: int = len(swc_feature) - len(swc_exclude)

        # len for faster execution
        length = self._hant_length(segment)

        segment_features = SegmentFeatures(segment, canto_feature, canto_exclude, swc_feature,
                                           swc_exclude, canto_feature_count, swc_feature_count, length)

        return segment_features

    def _judge_single_segment(self, segment: str) -> str:
        """
        Determine the language of a segment based on the presence of Cantonese and SWC features.

        If the Cantonese feature presence are above the threshold, and the Mandarin feature is below the threshold, then it's Cantonese.
        If the Cantonese feature presence are below the threshold, and the Mandarin feature is above the threshold, then it's SWC.
        If both Cantonese and SWC features are below the threshold, then it's Neutral text.
        If both Cantonese and SWC features are above the threshold, then it's Mixed.

        Args:
            segment (str): The segment of text to be judged.

        Returns:
            tuple: A tuple containing the language of the segment (Cantonese, SWC, Neutral, or Mixed), 
                the count of Cantonese features in the segment, the count of SWC features in the segment, 
                and the length of the segment in Han characters.
        """
        features: SegmentFeatures = self._get_segment_features(segment)

        num_all_features: int = features.canto_feature_count + features.swc_feature_count

        lack_swc: bool = features.swc_feature_count <= math.floor(
            self.swc_tolerance * features.length)
        lack_canto: bool = features.canto_feature_count <= math.floor(
            self.canto_tolerance * features.length)

        if num_all_features == 0 or (lack_canto and lack_swc):
            return "Neutral"
        else:
            has_canto: bool = features.canto_feature_count >= math.ceil(
                self.canto_presence * features.length)
            has_swc: bool = features.swc_feature_count >= math.ceil(
                self.swc_presence * features.length)

            canto_pref: bool = features.canto_feature_count / num_all_features - \
                features.swc_feature_count / num_all_features > 0.9
            swc_pref: bool = features.swc_feature_count / num_all_features - \
                features.canto_feature_count / num_all_features > 0.9

            if canto_pref and not has_swc:
                return "Cantonese"
            elif swc_pref and not has_canto:
                return "SWC"
            else:
                return "Mixed"

    def _judge_segments(self, document: str) -> str:
        """
        Given a list of segments:
        1. If >95% of the segments are Neutral, the overall judgement is Neutral
        2. If Neutral + Cantonese takes up >95%, then overall it is Cantonese
        3. If Neutral + SWC takes up > 95%, then overall it is SWC
        4. Otherwise, it is Mixed.

        Args:
            segments (list): A list of segments to be judged.

        Returns:
            str: The aggregated judgement of the segments.
        """
        segments = filter(lambda x: x.strip(),
                          ALL_DELIMITERS_RE.split(document))

        judgements = [self._judge_single_segment(
            segment) for segment in segments]

        judgements_counter: Counter = Counter(judgements)

        canto_seg_count: int = judgements_counter["Cantonese"]
        swc_seg_count: int = judgements_counter["SWC"]
        neutral_seg_count: int = judgements_counter["Neutral"]

        # 95% threshold
        threshold = math.ceil(sum(judgements_counter.values()) * 0.95)

        canto_only: bool = canto_seg_count + neutral_seg_count >= threshold
        swc_only: bool = swc_seg_count + neutral_seg_count >= threshold
        neutral_only: bool = neutral_seg_count >= threshold

        if neutral_only:
            return "Neutral"
        elif canto_only:
            return "Cantonese"
        elif swc_only:
            return "SWC"
        else:
            return "Mixed"

    def _judge_document(self, document: str) -> str:
        if self.split_seg:
            return self._judge_segments(document)
        else:
            return self._judge_single_segment(document)

    def _judge_matrix_quotes(self, document: str) -> str:
        """
        Judge the language of a document with quotes.

        Args:
            document (str): The document to be judged.
        Returns:
            tuple: A tuple containing the language of the document, the Cantonese ratio, and the SWC ratio.
        """
        matrix, quotes = self._separate_quotes(document)

        if matrix == "…":
            # Matrix is empty, entire input is a quote
            return self._judge_document(ALL_QUOTEMARKS_RE.sub("", quotes))
        elif quotes == "":
            # No quotes
            return self._judge_document(matrix)
        else:
            matrix_judgement = self._judge_document(matrix)
            quotes_judgement = self._judge_document(quotes)

            if matrix_judgement == quotes_judgement:
                return matrix_judgement
            elif matrix_judgement == 'Neutral':
                return quotes_judgement
            elif quotes_judgement == 'Neutral':
                return matrix_judgement
            elif matrix_judgement == 'SWC' and quotes_judgement == 'Cantonese':
                judgement = "CantoneseQuotesInSWC"
            elif matrix_judgement == 'SWC' and quotes_judgement == 'Mixed':
                judgement = "MixedQuotesInSWC"
            else:
                judgement = "Mixed"

            # canto_ratio = f'[M]{_c1}:[Q]{_c2}'
            # swc_ratio = f'[M]{_s1}:[Q]{_s2}'
            return judgement

    def judge(self, document: str) -> str:
        """
        The only exposed api. Judge the language of a document.

        Args:
            document (str): The document to be judged.

        Returns:
            str: The final judgement.
        """
        if self.get_quote:
            return self._judge_matrix_quotes(document)
        else:
            return self._judge_document(document)
