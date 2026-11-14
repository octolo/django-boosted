"""Formatting utilities for django-boosted."""

from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

_REVEAL_JS = (
    "const w=this.previousElementSibling,"
    "m=w.querySelector('.boost-secret-mask'),"
    "v=w.querySelector('.boost-secret-value'),"
    "s=v.style.display!=='none';"
    "v.style.display=s?'none':'';"
    "m.style.display=s?'':'none';"
    "this.setAttribute('aria-expanded',String(!s));"
)


def reveal_html(content, mask="••••••••"):
    """Wrap read-only content so it is masked by default with a reveal toggle."""
    return format_html(
        '<span class="boost-reveal">'
        '<span class="boost-secret">'
        '<span class="boost-secret-mask">{}</span>'
        '<span class="boost-secret-value" style="display:none">{}</span>'
        "</span>"
        '<button type="button" class="boost-reveal-toggle" aria-label="{}" '
        'aria-expanded="false" onclick="' + _REVEAL_JS + '">'
        '<img src="{}" alt="">'
        "</button>"
        "</span>",
        mask,
        content,
        _("Reveal"),
        static("admin/img/icon-viewlink.svg"),
    )


def boolean_icon_html(value):
    """Return the HTML image (admin icon) for a boolean value."""
    is_ok = value == "✓" if isinstance(value, str) else bool(value)
    icon = "icon-yes.svg" if is_ok else "icon-no.svg"
    return format_html(
        '<img src="{}" alt="{}">',
        static(f"admin/img/{icon}"),
        _("Yes") if is_ok else _("No"),
    )


def format_label(
    text: str,
    label_type: str = "info",
    size: str | None = None,
    link: str | None = None,
    style: str | None = None,
) -> str:
    classes = ["boost-label"]
    valid_types = [
        "success",
        "info",
        "warning",
        "danger",
        "primary",
        "secondary",
        "default",
    ]
    if label_type.lower() in valid_types:
        classes.append(label_type.lower())
    else:
        classes.append("info")
    if size and size.lower() in ["small", "big"]:
        classes.append(size.lower())
    if link:
        classes.append("link")
    css_class = " ".join(classes)
    tag = "a" if link else "span"
    if link and style:
        return format_html(
            '<{} href="{}" class="{}" style="{}">{}</{}>',
            tag,
            link,
            css_class,
            style,
            text,
            tag,
        )
    if link:
        return format_html(
            '<{} href="{}" class="{}">{}</{}>', tag, link, css_class, text, tag
        )
    if style:
        return format_html(
            '<{} class="{}" style="{}">{}</{}>', tag, css_class, style, text, tag
        )
    return format_html('<{} class="{}">{}</{}>', tag, css_class, text, tag)


def format_status(
    name: str, status: bool, style: str | None = None, link: str | None = None
) -> str:
    icon = "✓" if status else "✗"
    status_class = "success" if status else "error"
    content = format_html(
        '<span class="boost-status {}" style="{}">{}</span> <code>{}</code>',
        status_class,
        style,
        icon,
        name,
    )
    if not link:
        return format_html("<span>{}</span>", content)
    return format_html(
        '<a href="{}">{}</a>',
        link,
        content,
    )


def format_with_help_text(html_content: str, help_text: str | None = None) -> str:
    if help_text:
        return format_html(
            '{}<br><small class="help">{}</small>', html_content, help_text
        )
    return html_content
