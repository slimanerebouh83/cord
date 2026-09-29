"""
CORD UI - Internationalization Engine (i18n)
Supports 9 full languages: Arabic, English, French, Spanish, German, Chinese, Japanese, Russian, Turkish.
"""

from __future__ import annotations
from typing import Dict, Any, Optional

# Supported language codes, flags, and native display names
LANGUAGES: Dict[str, Dict[str, str]] = {
    "en": {"name": "English", "flag": "🇺🇸", "dir": "ltr"},
    "fr": {"name": "Français", "flag": "🇫🇷", "dir": "ltr"},
    "es": {"name": "Español", "flag": "🇪🇸", "dir": "ltr"},
    "de": {"name": "Deutsch", "flag": "🇩🇪", "dir": "ltr"},
    "zh": {"name": "中文 (简体)", "flag": "🇨🇳", "dir": "ltr"},
    "ja": {"name": "日本語", "flag": "🇯🇵", "dir": "ltr"},
    "ru": {"name": "Русский", "flag": "🇷🇺", "dir": "ltr"},
    "tr": {"name": "Türkçe", "flag": "🇹🇷", "dir": "ltr"},
    "ar": {"name": "العربية", "flag": "🇸🇦", "dir": "rtl"},
}

# Complete translation strings across all languages
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "welcome_title": {
        "en": "Welcome to CORD — Autonomous Engineering & Computer-Use Agent",
        "fr": "Bienvenue sur CORD — Agent d'ingénierie autonome et contrôle du système",
        "es": "Bienvenido a CORD — Agente de ingeniería autónomo y control del sistema",
        "de": "Willkommen bei CORD — Autonomer Engineering- und Computer-Use-Agent",
        "zh": "欢迎使用 CORD — 自主工程与计算机控制智能体",
        "ja": "CORD へようこそ — 自律型エンジニアリング＆コンピュータ制御エージェント",
        "ru": "Добро пожаловать в CORD — Автономный агент разработки и управления ПК",
        "tr": "CORD'a Hoş Geldiniz — Otonom Mühendislik ve Bilgisayar Kontrol Ajanı",
        "ar": "مرحباً بك في CORD — وكيل الهندسة المستقلة والتحكم بالحاسوب",
    },
    "choose_language": {
        "en": "Please choose your preferred language to continue:",
        "fr": "Veuillez choisir votre langue préférée pour continuer :",
        "es": "Por favor, elija su idioma preferido para continuar:",
        "de": "Bitte wählen Sie Ihre bevorzugte Sprache aus, um fortzufahren:",
        "zh": "请选择您的首选语言以继续：",
        "ja": "続行するには希望の言語を選択してください：",
        "ru": "Пожалуйста, выберите предпочитаемый язык для продолжения:",
        "tr": "Devam etmek için lütfen tercih ettiğiniz dili seçin:",
        "ar": "يرجى اختيار لغتك المفضلة للمتابعة:",
    },
    "language_set": {
        "en": "Language successfully set to: {lang}",
        "fr": "Langue définie avec succès sur : {lang}",
        "es": "Idioma configurado con éxito en: {lang}",
        "de": "Sprache erfolgreich eingestellt auf: {lang}",
        "zh": "语言已成功设置为：{lang}",
        "ja": "言語が正常に設定されました: {lang}",
        "ru": "Язык успешно установлен на: {lang}",
        "tr": "Dil başarıyla ayarlandı: {lang}",
    },
    "input_box_title": {
        "en": "Chat Input",
        "fr": "Entrée CORD",
        "es": "Entrada CORD",
        "de": "CORD Eingabe",
        "zh": "CORD 输入",
        "ja": "CORD 入力",
        "ru": "Ввод CORD",
        "tr": "CORD Girişi",
        "ar": "إدخال الدردشة",
    },
    "input_placeholder": {
        "en": "Type your message or instruction here...",
        "fr": "Tapez votre message ou instruction ici...",
        "es": "Escriba su mensaje o instrucción aquí...",
        "de": "Geben Sie hier Ihre Nachricht oder Anweisung ein...",
        "zh": "在此输入您的消息或指令...",
        "ja": "ここにメッセージまたは指示を入力...",
        "ru": "Введите ваше сообщение или команду здесь...",
        "tr": "Mesajınızı veya talimatınızı buraya yazın...",
        "ar": "اكتب رسالتك أو تعليماتك هنا...",
    },
    "thinking_live": {
        "en": "⚡ Live Reasoning & Engineering Synthesis...",
        "fr": "⚡ Raisonnement en direct et synthèse...",
        "es": "⚡ Razonamiento en vivo y síntesis...",
        "de": "⚡ Live-Überlegungen & Analyse...",
        "zh": "⚡ 实时深度思考与架构推理...",
        "ja": "⚡ リアルタイム推論＆アーキテクチャ解析...",
        "ru": "⚡ Анализ и рассуждение в реальном времени...",
        "tr": "⚡ Canlı Akıl Yürütme ve Mühendislik Analizi...",
        "ar": "⚡ تحليل واستدلال مباشر...",
    },
    "thinking_complete": {
        "en": "Reasoning complete ({duration:.1f}s)",
        "fr": "Raisonnement terminé ({duration:.1f}s)",
        "es": "Razonamiento completado ({duration:.1f}s)",
        "de": "Überlegung abgeschlossen ({duration:.1f}s)",
        "zh": "思考完成 ({duration:.1f}秒)",
        "ja": "推論完了 ({duration:.1f}秒)",
        "ru": "Рассуждение завершено ({duration:.1f}с)",
        "tr": "Düşünme tamamlandı ({duration:.1f}sn)",
    },
    "permission_required": {
        "en": "Permission Required",
        "fr": "Autorisation requise",
        "es": "Permiso requerido",
        "de": "Berechtigung erforderlich",
        "zh": "需要权限授权",
        "ja": "実行許可が必要です",
        "ru": "Требуется разрешение",
        "tr": "İzin Gerekli",
        "ar": "مطلوب إذن",
    },
    "permission_allow": {
        "en": "[y] Allow",
        "fr": "[y] Autoriser",
        "es": "[y] Permitir",
        "de": "[y] Erlauben",
        "zh": "[y] 允许",
        "ja": "[y] 許可",
        "ru": "[y] Разрешить",
        "tr": "[y] İzin Ver",
        "ar": "[y] السماح",
    },
    "permission_always": {
        "en": "[a] Always allow for session",
        "fr": "[a] Toujours autoriser pour la session",
        "es": "[a] Permitir siempre en esta sesión",
        "de": "[a] Immer für diese Sitzung erlauben",
        "zh": "[a] 本会话永久允许",
        "ja": "[a] このセッション中は常に許可",
        "ru": "[a] Всегда разрешать в этой сессии",
        "tr": "[a] Bu oturum için her zaman izin ver",
        "ar": "[a] السماح دائماً لهذه الجلسة",
    },
    "permission_deny": {
        "en": "[n] Deny",
        "fr": "[n] Refuser",
        "es": "[n] Denegar",
        "de": "[n] Ablehnen",
        "zh": "[n] 拒绝",
        "ja": "[n] 拒否",
        "ru": "[n] Отклонить",
        "tr": "[n] Reddet",
        "ar": "[n] رفض",
    },
    "tool_executing": {
        "en": "Executing tool: {name}",
        "fr": "Exécution de l'outil : {name}",
        "es": "Ejecutando herramienta: {name}",
        "de": "Tool wird ausgeführt: {name}",
        "zh": "正在执行工具：{name}",
        "ja": "ツール実行中: {name}",
        "ru": "Выполнение инструмента: {name}",
        "tr": "Araç çalıştırılıyor: {name}",
        "ar": "تنفيذ الأداة: {name}",
    },
    "tool_finished": {
        "en": "Tool completed: {name}",
        "fr": "Outil terminé : {name}",
        "es": "Herramienta completada: {name}",
        "de": "Tool abgeschlossen: {name}",
        "zh": "工具执行完毕：{name}",
        "ja": "ツール完了: {name}",
        "ru": "Инструмент завершен: {name}",
        "tr": "Araç tamamlandı: {name}",
        "ar": "اكتملت الأداة: {name}",
    },
    "tool_failed": {
        "en": "Tool execution failed: {name}",
        "fr": "Échec de l'outil : {name}",
        "es": "Fallo en la herramienta: {name}",
        "de": "Tool fehlgeschlagen: {name}",
        "zh": "工具执行失败：{name}",
        "ja": "ツール失敗: {name}",
        "ru": "Ошибка инструмента: {name}",
        "tr": "Araç başarısız oldu: {name}",
        "ar": "فشل تنفيذ الأداة: {name}",
    },
    "goodbye": {
        "en": "Goodbye! Happy coding with CORD.",
        "fr": "Au revoir ! Bon codage avec CORD.",
        "es": "¡Hasta pronto! Feliz programación con CORD.",
        "de": "Auf Wiedersehen! Viel Erfolg beim Coden mit CORD.",
        "zh": "再见！祝您使用 CORD 编程愉快。",
        "ja": "さようなら！CORD で快適なコーディングを。",
        "ru": "До свидания! Удачной разработки с CORD.",
        "tr": "Görüşmek üzere! CORD ile keyifli kodlamalar.",
        "ar": "وداعاً! برمجة سعيدة مع CORD.",
    },
    "input_mode_changed": {
        "en": "Input engine switched to: {mode}",
        "fr": "Moteur d'entrée changé pour : {mode}",
        "es": "Motor de entrada cambiado a: {mode}",
        "de": "Eingabemodus gewechselt zu: {mode}",
        "zh": "输入引擎已切换为：{mode}",
        "ja": "入力エンジンが切り替わりました: {mode}",
        "ru": "Режим ввода переключен на: {mode}",
        "tr": "Giriş motoru değiştirildi: {mode}",
        "ar": "تم تبديل محرك الإدخال إلى: {mode}",
    },
    "thinking_mode_changed": {
        "en": "Thinking mode switched to: {mode}",
        "fr": "Mode de pensée changé pour : {mode}",
        "es": "Modo de pensamiento cambiado a: {mode}",
        "de": "Überlegungsmodus gewechselt zu: {mode}",
        "zh": "思考模式已切换为：{mode}",
        "ja": "推論モードが切り替わりました: {mode}",
        "ru": "Режим рассуждений переключен на: {mode}",
        "tr": "Düşünme modu değiştirildi: {mode}",
        "ar": "تم تبديل وضع التفكير إلى: {mode}",
    }
}

class I18nManager:
    """Singleton Internationalization manager."""
    _instance: Optional[I18nManager] = None

    def __init__(self, default_lang: str = "en"):
        self.current_lang = default_lang if default_lang in LANGUAGES else "en"

    @classmethod
    def get_instance(cls, default_lang: str = "en") -> I18nManager:
        if cls._instance is None:
            cls._instance = I18nManager(default_lang=default_lang)
        return cls._instance

    def set_language(self, lang_code: str) -> bool:
        clean = lang_code.strip().lower()
        # Direct code match
        if clean in LANGUAGES:
            self.current_lang = clean
            return True
        # Match by name or alias
        aliases: Dict[str, str] = {
            "english": "en", "en": "en",
            "french": "fr", "français": "fr", "fr": "fr",
            "spanish": "es", "español": "es", "es": "es",
            "german": "de", "deutsch": "de", "de": "de",
            "chinese": "zh", "中文": "zh", "zh": "zh",
            "japanese": "ja", "日本語": "ja", "ja": "ja",
            "russian": "ru", "русский": "ru", "ru": "ru",
            "turkish": "tr", "türkçe": "tr", "tr": "tr",
            "arabic": "ar", "العربية": "ar", "ar": "ar",
        }
        if clean in aliases:
            self.current_lang = aliases[clean]
            return True
        return False

    def t(self, key: str, **kwargs) -> str:
        """Translates a key into current language with formatted kwargs."""
        entry = TRANSLATIONS.get(key)
        if not entry:
            return key
        text = entry.get(self.current_lang) or entry.get("en") or key
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    @property
    def is_rtl(self) -> bool:
        return LANGUAGES.get(self.current_lang, {}).get("dir") == "rtl"


i18n = I18nManager.get_instance()

def t(key: str, **kwargs) -> str:
    """Convenience helper for translation."""
    return i18n.t(key, **kwargs)
