/* @ds-bundle: {"format":4,"namespace":"SuperTradesDesignSystem_4b8c0b","components":[{"name":"Badge","sourcePath":"components/display/Badge.jsx"},{"name":"Card","sourcePath":"components/display/Card.jsx"},{"name":"Tabs","sourcePath":"components/display/Tabs.jsx"},{"name":"Toast","sourcePath":"components/display/Toast.jsx"},{"name":"Button","sourcePath":"components/forms/Button.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Switch","sourcePath":"components/forms/Switch.jsx"},{"name":"ConfidenceMeter","sourcePath":"components/trading/ConfidenceMeter.jsx"},{"name":"DataTable","sourcePath":"components/trading/DataTable.jsx"},{"name":"SignalCard","sourcePath":"components/trading/SignalCard.jsx"},{"name":"StatCard","sourcePath":"components/trading/StatCard.jsx"},{"name":"TickerChip","sourcePath":"components/trading/TickerChip.jsx"}],"sourceHashes":{"components/display/Badge.jsx":"59c1225521da","components/display/Card.jsx":"1339711a40f1","components/display/Tabs.jsx":"01363461c024","components/display/Toast.jsx":"894af707ee44","components/forms/Button.jsx":"60ffc942f43f","components/forms/Input.jsx":"efd5d5bce195","components/forms/Select.jsx":"ae755905a08d","components/forms/Switch.jsx":"b3b8a781f2e6","components/trading/ConfidenceMeter.jsx":"c3abda7e7071","components/trading/DataTable.jsx":"52ee5c47a60a","components/trading/SignalCard.jsx":"95eca4e2e09f","components/trading/StatCard.jsx":"4a22bdf5cc01","components/trading/TickerChip.jsx":"785b275f21d6","design_handoff_supertrades_terminal/doc-page.js":"62024d965071","design_handoff_supertrades_terminal/ui_kits/terminal/data.js":"f98dc6578d79","handoff/doc-page.js":"62024d965071","ui_kits/mobile/ios-frame.jsx":"be3343be4b51","ui_kits/mobile/screens.jsx":"6ce605a09425","ui_kits/terminal/ChartView.jsx":"86ebd588a306","ui_kits/terminal/GexView.jsx":"badc7f4bce87","ui_kits/terminal/Portfolio.jsx":"26ca6ff763f8","ui_kits/terminal/Scanner.jsx":"d5dc0b2a0979","ui_kits/terminal/Settings.jsx":"aeda8b911b27","ui_kits/terminal/SignalDetail.jsx":"a13013c0c1b3","ui_kits/terminal/SignalsFeed.jsx":"6975147d3faa","ui_kits/terminal/chrome.jsx":"3f0109df6a5b","ui_kits/terminal/data.js":"f98dc6578d79"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.SuperTradesDesignSystem_4b8c0b = window.SuperTradesDesignSystem_4b8c0b || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/display/Badge.jsx
try { (() => {
const TONES = {
  long: {
    background: 'var(--green-dim)',
    color: 'var(--green-400)',
    border: 'var(--green-line)'
  },
  short: {
    background: 'var(--red-dim)',
    color: 'var(--red-400)',
    border: 'var(--red-line)'
  },
  warning: {
    background: 'var(--amber-dim)',
    color: 'var(--amber-500)',
    border: 'rgba(255,176,32,0.35)'
  },
  info: {
    background: 'var(--cyan-dim)',
    color: 'var(--cyan-500)',
    border: 'rgba(43,217,244,0.35)'
  },
  neutral: {
    background: 'var(--surface-raised)',
    color: 'var(--text-secondary)',
    border: 'var(--border-default)'
  }
};
function Badge({
  tone = 'neutral',
  dot = false,
  pulse = false,
  children,
  style
}) {
  const t = TONES[tone] || TONES.neutral;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      padding: '3px 8px',
      whiteSpace: 'nowrap',
      borderRadius: 'var(--radius-xs)',
      background: t.background,
      color: t.color,
      border: `1px solid ${t.border}`,
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      ...style
    }
  }, dot && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: 'currentColor',
      animation: pulse ? 'st-badge-pulse 1.6s infinite' : 'none'
    }
  }), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Badge.jsx", error: String((e && e.message) || e) }); }

// components/display/Card.jsx
try { (() => {
const {
  useState
} = React;
function Card({
  title,
  meta,
  live = false,
  direction = null,
  hoverable = false,
  padding = 16,
  children,
  onClick,
  style
}) {
  const [hover, setHover] = useState(false);
  const dirBorder = direction === 'long' ? 'var(--green-line)' : direction === 'short' ? 'var(--red-line)' : null;
  const glow = live ? direction === 'short' ? 'var(--glow-red)' : 'var(--glow-green)' : null;
  const raised = hoverable && hover;
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      background: raised ? 'var(--surface-raised)' : 'var(--surface-card)',
      border: `1px solid ${dirBorder || (raised ? 'var(--border-strong)' : 'var(--border-hairline)')}`,
      borderRadius: 'var(--radius-md)',
      boxShadow: glow ? `var(--shadow-card), ${glow}` : raised ? 'var(--shadow-raised)' : 'var(--shadow-card)',
      padding,
      cursor: onClick ? 'pointer' : undefined,
      transition: 'background var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out)',
      ...style
    }
  }, (title || meta) && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      justifyContent: 'space-between',
      gap: 8,
      marginBottom: 10
    }
  }, title && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-heading)',
      color: 'var(--text-primary)'
    }
  }, title), meta && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, meta)), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Card.jsx", error: String((e && e.message) || e) }); }

// components/display/Tabs.jsx
try { (() => {
const {
  useState
} = React;
function Tabs({
  tabs = [],
  active,
  onChange,
  size = 'md',
  style
}) {
  const [hovered, setHovered] = useState(null);
  const pad = size === 'sm' ? '5px 10px' : '7px 14px';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'inline-flex',
      gap: 2,
      padding: 3,
      background: 'var(--surface-inset)',
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-sm)',
      ...style
    }
  }, tabs.map(t => {
    const tab = typeof t === 'string' ? {
      id: t,
      label: t
    } : t;
    const isActive = tab.id === active;
    const isHover = hovered === tab.id;
    return /*#__PURE__*/React.createElement("button", {
      key: tab.id,
      onClick: () => onChange && onChange(tab.id),
      onMouseEnter: () => setHovered(tab.id),
      onMouseLeave: () => setHovered(null),
      style: {
        padding: pad,
        border: 'none',
        borderRadius: 4,
        cursor: 'pointer',
        background: isActive ? 'var(--surface-raised)' : 'transparent',
        color: isActive ? 'var(--green-400)' : isHover ? 'var(--text-primary)' : 'var(--text-secondary)',
        font: size === 'sm' ? '600 11px/1 var(--font-sans)' : '600 13px/1 var(--font-sans)',
        boxShadow: isActive ? 'inset 0 0 0 1px var(--border-default)' : 'none',
        transition: 'color var(--duration-fast) var(--ease-out), background var(--duration-fast) var(--ease-out)'
      }
    }, tab.label);
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Tabs.jsx", error: String((e && e.message) || e) }); }

// components/display/Toast.jsx
try { (() => {
const TONES = {
  success: {
    color: 'var(--green-400)',
    border: 'var(--green-line)',
    glow: 'var(--glow-green)'
  },
  danger: {
    color: 'var(--red-400)',
    border: 'var(--red-line)',
    glow: 'var(--glow-red)'
  },
  warning: {
    color: 'var(--amber-500)',
    border: 'rgba(255,176,32,0.35)',
    glow: 'var(--glow-amber)'
  },
  info: {
    color: 'var(--cyan-500)',
    border: 'rgba(43,217,244,0.35)',
    glow: 'none'
  }
};
function Toast({
  tone = 'info',
  title,
  detail,
  time,
  onDismiss,
  style
}) {
  const t = TONES[tone] || TONES.info;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 10,
      width: 340,
      padding: '12px 14px',
      background: 'var(--surface-overlay)',
      backdropFilter: 'var(--blur-overlay)',
      WebkitBackdropFilter: 'var(--blur-overlay)',
      border: `1px solid ${t.border}`,
      borderRadius: 'var(--radius-md)',
      boxShadow: `var(--shadow-overlay)${t.glow !== 'none' ? `, ${t.glow}` : ''}`,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: t.color,
      marginTop: 5,
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      gap: 8,
      alignItems: 'baseline'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-strong)',
      color: t.color
    }
  }, title), time && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, time)), detail && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data)',
      color: 'var(--text-secondary)'
    }
  }, detail)), onDismiss && /*#__PURE__*/React.createElement("button", {
    onClick: onDismiss,
    style: {
      background: 'none',
      border: 'none',
      color: 'var(--text-muted)',
      cursor: 'pointer',
      fontSize: 14,
      padding: 0,
      lineHeight: 1
    }
  }, "\xD7"));
}
Object.assign(__ds_scope, { Toast });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Toast.jsx", error: String((e && e.message) || e) }); }

// components/forms/Button.jsx
try { (() => {
const {
  useState
} = React;
const VARIANTS = {
  primary: {
    background: 'var(--green-500)',
    color: 'var(--text-on-accent)',
    border: '1px solid transparent'
  },
  secondary: {
    background: 'var(--surface-raised)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-default)'
  },
  ghost: {
    background: 'transparent',
    color: 'var(--text-secondary)',
    border: '1px solid transparent'
  },
  danger: {
    background: 'var(--red-500)',
    color: '#FFECEC',
    border: '1px solid transparent'
  },
  long: {
    background: 'var(--green-dim)',
    color: 'var(--green-400)',
    border: '1px solid var(--green-line)'
  },
  short: {
    background: 'var(--red-dim)',
    color: 'var(--red-400)',
    border: '1px solid var(--red-line)'
  }
};
const HOVER = {
  primary: {
    background: 'var(--green-400)'
  },
  secondary: {
    background: 'var(--surface-raised)',
    border: '1px solid var(--border-strong)'
  },
  ghost: {
    background: 'var(--surface-raised)',
    color: 'var(--text-primary)'
  },
  danger: {
    background: 'var(--red-400)'
  },
  long: {
    background: 'rgba(0, 230, 123, 0.2)'
  },
  short: {
    background: 'rgba(255, 59, 59, 0.2)'
  }
};
const SIZES = {
  sm: {
    height: 'var(--control-height-sm)',
    padding: '0 10px',
    font: '600 12px/1 var(--font-sans)'
  },
  md: {
    height: 'var(--control-height)',
    padding: '0 14px',
    font: '600 13px/1 var(--font-sans)'
  },
  lg: {
    height: 'var(--control-height-lg)',
    padding: '0 18px',
    font: '600 14px/1 var(--font-sans)'
  }
};
function Button({
  variant = 'primary',
  size = 'md',
  disabled = false,
  fullWidth = false,
  icon = null,
  children,
  onClick,
  style
}) {
  const [hover, setHover] = useState(false);
  const base = VARIANTS[variant] || VARIANTS.primary;
  const hov = hover && !disabled ? HOVER[variant] || {} : {};
  return /*#__PURE__*/React.createElement("button", {
    onClick: disabled ? undefined : onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    disabled: disabled,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
      borderRadius: 'var(--radius-sm)',
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.45 : 1,
      width: fullWidth ? '100%' : undefined,
      transition: 'background var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out)',
      ...SIZES[size],
      ...base,
      ...hov,
      ...style
    }
  }, icon, children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Button.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
const {
  useState
} = React;
function Input({
  label,
  value,
  defaultValue,
  onChange,
  placeholder,
  prefix,
  suffix,
  mono = false,
  size = 'md',
  disabled = false,
  style
}) {
  const [focus, setFocus] = useState(false);
  const h = size === 'sm' ? 'var(--control-height-sm)' : size === 'lg' ? 'var(--control-height-lg)' : 'var(--control-height)';
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-secondary)'
    }
  }, label), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      height: h,
      padding: '0 10px',
      background: 'var(--surface-inset)',
      borderRadius: 'var(--radius-sm)',
      border: `1px solid ${focus ? 'var(--border-focus)' : 'var(--border-default)'}`,
      boxShadow: focus ? 'var(--glow-green)' : 'none',
      opacity: disabled ? 0.45 : 1,
      transition: 'border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out)'
    }
  }, prefix && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, prefix), /*#__PURE__*/React.createElement("input", {
    value: value,
    defaultValue: defaultValue,
    placeholder: placeholder,
    disabled: disabled,
    onChange: onChange ? e => onChange(e.target.value) : undefined,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      flex: 1,
      minWidth: 0,
      background: 'transparent',
      border: 'none',
      outline: 'none',
      color: 'var(--text-primary)',
      font: mono ? 'var(--type-data)' : 'var(--type-body)',
      fontVariantNumeric: 'tabular-nums'
    }
  }), suffix && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, suffix)));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
const {
  useState
} = React;
function Select({
  label,
  value,
  defaultValue,
  onChange,
  options = [],
  size = 'md',
  disabled = false,
  style
}) {
  const [focus, setFocus] = useState(false);
  const h = size === 'sm' ? 'var(--control-height-sm)' : size === 'lg' ? 'var(--control-height-lg)' : 'var(--control-height)';
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-secondary)'
    }
  }, label), /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      height: h,
      position: 'relative',
      background: 'var(--surface-inset)',
      borderRadius: 'var(--radius-sm)',
      border: `1px solid ${focus ? 'var(--border-focus)' : 'var(--border-default)'}`,
      boxShadow: focus ? 'var(--glow-green)' : 'none',
      opacity: disabled ? 0.45 : 1,
      transition: 'border-color var(--duration-fast) var(--ease-out)'
    }
  }, /*#__PURE__*/React.createElement("select", {
    value: value,
    defaultValue: defaultValue,
    disabled: disabled,
    onChange: onChange ? e => onChange(e.target.value) : undefined,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      appearance: 'none',
      WebkitAppearance: 'none',
      width: '100%',
      height: '100%',
      background: 'transparent',
      border: 'none',
      outline: 'none',
      cursor: 'pointer',
      color: 'var(--text-primary)',
      font: 'var(--type-body)',
      padding: '0 28px 0 10px'
    }
  }, options.map(o => {
    const opt = typeof o === 'string' ? {
      value: o,
      label: o
    } : o;
    return /*#__PURE__*/React.createElement("option", {
      key: opt.value,
      value: opt.value,
      style: {
        background: '#0D1512'
      }
    }, opt.label);
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      right: 10,
      pointerEvents: 'none',
      color: 'var(--text-muted)',
      fontSize: 10
    }
  }, "\u25BE")));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/forms/Switch.jsx
try { (() => {
function Switch({
  checked = false,
  onChange,
  label,
  disabled = false,
  style
}) {
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 10,
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.45 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    onClick: disabled || !onChange ? undefined : () => onChange(!checked),
    role: "switch",
    "aria-checked": checked,
    style: {
      width: 36,
      height: 20,
      borderRadius: 'var(--radius-full)',
      position: 'relative',
      flexShrink: 0,
      background: checked ? 'var(--green-500)' : 'var(--surface-inset)',
      border: `1px solid ${checked ? 'var(--green-500)' : 'var(--border-strong)'}`,
      boxShadow: checked ? 'var(--glow-green)' : 'none',
      transition: 'background var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      top: 2,
      left: checked ? 18 : 2,
      width: 14,
      height: 14,
      borderRadius: '50%',
      background: checked ? 'var(--text-on-accent)' : 'var(--text-secondary)',
      transition: 'left var(--duration-base) var(--ease-out), background var(--duration-base) var(--ease-out)'
    }
  })), label && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body)',
      color: 'var(--text-primary)'
    }
  }, label));
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Switch.jsx", error: String((e && e.message) || e) }); }

// components/trading/ConfidenceMeter.jsx
try { (() => {
function ConfidenceMeter({
  value = 0,
  label = 'Confidence',
  compact = false,
  style
}) {
  const v = Math.max(0, Math.min(100, value));
  const color = v >= 70 ? 'var(--green-500)' : v >= 45 ? 'var(--amber-500)' : 'var(--red-500)';
  const tier = v >= 70 ? 'HIGH' : v >= 45 ? 'MED' : 'LOW';
  if (compact) {
    return /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        ...style
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 48,
        height: 4,
        borderRadius: 2,
        background: 'var(--surface-inset)',
        overflow: 'hidden'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'block',
        width: `${v}%`,
        height: '100%',
        background: color,
        transition: 'width var(--duration-slow) var(--ease-out)'
      }
    })), /*#__PURE__*/React.createElement("span", {
      style: {
        font: 'var(--type-data-sm)',
        color
      }
    }, v));
  }
  const r = 34;
  const circ = Math.PI * r; // semicircle
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'inline-flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 2,
      ...style
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "88",
    height: "52",
    viewBox: "0 0 88 52"
  }, /*#__PURE__*/React.createElement("path", {
    d: `M 10 46 A ${r} ${r} 0 0 1 78 46`,
    fill: "none",
    stroke: "var(--surface-inset)",
    strokeWidth: "7",
    strokeLinecap: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: `M 10 46 A ${r} ${r} 0 0 1 78 46`,
    fill: "none",
    stroke: color,
    strokeWidth: "7",
    strokeLinecap: "round",
    strokeDasharray: `${v / 100 * circ} ${circ}`,
    style: {
      transition: 'stroke-dasharray var(--duration-slow) var(--ease-out)',
      filter: `drop-shadow(0 0 6px ${color})`
    }
  }), /*#__PURE__*/React.createElement("text", {
    x: "44",
    y: "42",
    textAnchor: "middle",
    fill: "var(--text-primary)",
    style: {
      font: '700 18px var(--font-mono)'
    }
  }, v)), /*#__PURE__*/React.createElement("span", {
    title: `${label} ${v}`,
    style: {
      width: 88,
      textAlign: 'center',
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color,
      whiteSpace: 'nowrap'
    }
  }, tier));
}
Object.assign(__ds_scope, { ConfidenceMeter });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/trading/ConfidenceMeter.jsx", error: String((e && e.message) || e) }); }

// components/trading/DataTable.jsx
try { (() => {
const {
  useState
} = React;
function DataTable({
  columns = [],
  rows = [],
  onRowClick,
  dense = false,
  style
}) {
  const [hover, setHover] = useState(-1);
  const pad = dense ? '6px 10px' : '9px 12px';
  return /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse',
      fontVariantNumeric: 'tabular-nums',
      ...style
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, columns.map(c => /*#__PURE__*/React.createElement("th", {
    key: c.key,
    style: {
      textAlign: c.align || 'left',
      padding: pad,
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)',
      borderBottom: '1px solid var(--border-default)',
      position: 'sticky',
      top: 0,
      background: 'var(--surface-card)'
    }
  }, c.label)))), /*#__PURE__*/React.createElement("tbody", null, rows.map((row, i) => /*#__PURE__*/React.createElement("tr", {
    key: i,
    onClick: onRowClick ? () => onRowClick(row, i) : undefined,
    onMouseEnter: () => setHover(i),
    onMouseLeave: () => setHover(-1),
    style: {
      background: hover === i ? 'var(--surface-raised)' : 'transparent',
      cursor: onRowClick ? 'pointer' : undefined,
      transition: 'background var(--duration-fast) var(--ease-out)'
    }
  }, columns.map(c => /*#__PURE__*/React.createElement("td", {
    key: c.key,
    style: {
      textAlign: c.align || 'left',
      padding: pad,
      font: c.mono === false ? 'var(--type-body)' : 'var(--type-data)',
      color: 'var(--text-primary)',
      borderBottom: '1px solid var(--border-hairline)'
    }
  }, typeof c.render === 'function' ? c.render(row[c.key], row) : row[c.key]))))));
}
Object.assign(__ds_scope, { DataTable });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/trading/DataTable.jsx", error: String((e && e.message) || e) }); }

// components/trading/SignalCard.jsx
try { (() => {
function Level({
  label,
  value,
  color
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)'
    }
  }, label), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-lg)',
      color: color || 'var(--text-primary)',
      fontVariantNumeric: 'tabular-nums',
      whiteSpace: 'nowrap'
    }
  }, value));
}
function SignalCard({
  direction = 'long',
  symbol,
  strategy,
  entry,
  stop,
  target,
  rr,
  confidence,
  time,
  live = false,
  status = null,
  factors = null,
  onClick,
  style
}) {
  const isLong = direction === 'long';
  const dirColor = isLong ? 'var(--green-500)' : 'var(--red-500)';
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClick,
    style: {
      background: 'var(--surface-card)',
      border: `1px solid ${isLong ? 'var(--green-line)' : 'var(--red-line)'}`,
      borderRadius: 'var(--radius-md)',
      boxShadow: live ? `var(--shadow-card), ${isLong ? 'var(--glow-green)' : 'var(--glow-red)'}` : 'var(--shadow-card)',
      padding: 16,
      width: 340,
      cursor: onClick ? 'pointer' : undefined,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      flexWrap: 'nowrap'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)',
      fontSize: 16,
      letterSpacing: 'var(--tracking-ticker)',
      color: 'var(--text-primary)'
    }
  }, symbol), /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    tone: isLong ? 'long' : 'short',
    dot: live,
    pulse: live
  }, isLong ? '▲ Long' : '▼ Short'), status && /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    tone: "neutral"
  }, status), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)',
      whiteSpace: 'nowrap'
    }
  }, time)), strategy && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-caption)',
      color: 'var(--text-secondary)',
      marginTop: -6
    }
  }, strategy), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3, auto)',
      gap: '8px 20px'
    }
  }, /*#__PURE__*/React.createElement(Level, {
    label: "Entry",
    value: entry,
    color: dirColor
  }), /*#__PURE__*/React.createElement(Level, {
    label: "Stop",
    value: stop
  }), /*#__PURE__*/React.createElement(Level, {
    label: "Target",
    value: target
  })), confidence != null && /*#__PURE__*/React.createElement(__ds_scope.ConfidenceMeter, {
    value: confidence
  })), factors && factors.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: 4
    }
  }, factors.map(f => {
    const isVeto = f.veto && !f.fired;
    return /*#__PURE__*/React.createElement("span", {
      key: f.label,
      title: f.detail,
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 6px',
        borderRadius: 'var(--radius-xs)',
        whiteSpace: 'nowrap',
        background: isVeto ? 'var(--red-dim)' : f.fired ? 'var(--green-dim)' : 'var(--surface-inset)',
        border: `1px solid ${isVeto ? 'var(--red-line)' : f.fired ? 'var(--green-line)' : 'var(--border-hairline)'}`,
        font: '600 10px/1.4 var(--font-mono)',
        letterSpacing: '0.03em',
        color: isVeto ? 'var(--red-400)' : f.fired ? 'var(--green-400)' : 'var(--text-disabled)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        color: isVeto ? 'var(--red-500)' : f.fired ? 'var(--green-500)' : 'var(--text-disabled)'
      }
    }, isVeto ? '✕' : f.fired ? '✓' : '○'), /*#__PURE__*/React.createElement("span", {
      style: {
        textTransform: 'uppercase',
        color: isVeto ? 'var(--red-400)' : f.fired ? 'var(--text-muted)' : 'var(--text-disabled)'
      }
    }, (f.kind || '').slice(0, 4)), f.label);
  })), rr && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      paddingTop: 10,
      borderTop: '1px solid var(--border-hairline)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)'
    }
  }, "R:R"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data)',
      color: 'var(--text-primary)',
      whiteSpace: 'nowrap'
    }
  }, rr)));
}
Object.assign(__ds_scope, { SignalCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/trading/SignalCard.jsx", error: String((e && e.message) || e) }); }

// components/trading/StatCard.jsx
try { (() => {
function StatCard({
  label,
  value,
  delta,
  deltaTone,
  spark = null,
  size = 'md',
  style
}) {
  const up = deltaTone ? deltaTone === 'up' : String(delta || '').trim().startsWith('+');
  const deltaColor = delta == null ? undefined : up ? 'var(--green-500)' : 'var(--red-500)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-card)',
      padding: size === 'sm' ? 12 : 16,
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      minWidth: 140,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)'
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 8,
      fontVariantNumeric: 'tabular-nums'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: size === 'sm' ? 'var(--type-data-lg)' : 'var(--type-data-xl)',
      color: 'var(--text-primary)',
      whiteSpace: 'nowrap'
    }
  }, value), delta != null && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data)',
      color: deltaColor,
      whiteSpace: 'nowrap'
    }
  }, up ? '▲' : '▼', " ", delta)), spark && spark.length > 1 && /*#__PURE__*/React.createElement(Sparkline, {
    data: spark,
    up: up
  }));
}
function Sparkline({
  data,
  up
}) {
  const w = 120,
    h = 28;
  const min = Math.min(...data),
    max = Math.max(...data);
  const pts = data.map((v, i) => `${i / (data.length - 1) * w},${h - 2 - (v - min) / (max - min || 1) * (h - 4)}`).join(' ');
  const color = up ? 'var(--green-500)' : 'var(--red-500)';
  return /*#__PURE__*/React.createElement("svg", {
    width: w,
    height: h,
    viewBox: `0 0 ${w} ${h}`,
    style: {
      overflow: 'visible'
    }
  }, /*#__PURE__*/React.createElement("polyline", {
    points: pts,
    fill: "none",
    stroke: color,
    strokeWidth: "1.5",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: pts.split(' ').pop().split(',')[0],
    cy: pts.split(' ').pop().split(',')[1],
    r: "2.5",
    fill: color,
    style: {
      filter: `drop-shadow(0 0 4px ${color})`
    }
  }));
}
Object.assign(__ds_scope, { StatCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/trading/StatCard.jsx", error: String((e && e.message) || e) }); }

// components/trading/TickerChip.jsx
try { (() => {
function TickerChip({
  symbol,
  price,
  change,
  size = 'md',
  style
}) {
  const up = typeof change === 'number' ? change >= 0 : String(change || '').trim().startsWith('+');
  const color = change == null ? 'var(--text-secondary)' : up ? 'var(--green-500)' : 'var(--red-500)';
  const changeText = typeof change === 'number' ? `${up ? '+' : '−'}${Math.abs(change).toFixed(2)}%` : change;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      padding: size === 'sm' ? '4px 8px' : '6px 10px',
      background: 'var(--surface-inset)',
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-xs)',
      fontVariantNumeric: 'tabular-nums',
      whiteSpace: 'nowrap',
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)',
      letterSpacing: 'var(--tracking-ticker)',
      color: 'var(--text-primary)'
    }
  }, symbol), price != null && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data)',
      color: 'var(--text-secondary)'
    }
  }, price), change != null && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data)',
      color
    }
  }, up ? '▲' : '▼', " ", changeText));
}
Object.assign(__ds_scope, { TickerChip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/trading/TickerChip.jsx", error: String((e && e.message) || e) }); }

// design_handoff_supertrades_terminal/doc-page.js
try { (() => {
// @ds-adherence-ignore -- omelette starter scaffold (raw elements/hex/px by design)
/* BEGIN USAGE */
/**
 * <doc-page> — paged-document shell for printable HTML.
 *
 * On screen the document renders as a single continuous sheet on a desk
 * background (Google Docs' pageless view): you scroll one tall page card.
 * There is no manual page-splitting — write the whole document as normal
 * flow inside <doc-page> and the browser's print engine paginates it at
 * export.
 *
 * At print the component injects `@page { size: …; margin: 0 }` (which
 * leaves Chrome no margin box to draw its date/URL/page-count header in)
 * and moves the visual margin onto the sheet's own padding, so the printed
 * page has the same inset you see on screen. Standard break-hygiene rules
 * (`break-inside: avoid` on figures, code blocks, images and table rows;
 * `orphans/widows: 3`) are applied so paragraphs and groups split cleanly.
 * On screen and at print, headings default to `text-wrap: balance` and
 * body text (p, li, blockquote, figcaption) to `text-wrap: pretty`, so
 * the document avoids widowed/orphaned words; the defaults have zero
 * specificity, so any text-wrap you declare on those elements wins.
 *
 * Usage:
 *   <style>doc-page:not(:defined){visibility:hidden}</style>
 *   <doc-page size="letter" margin="0.75in">
 *     <h1>Title</h1>
 *     <p>…body…</p>
 *   </doc-page>
 *   <script src="doc-page.js"></script>
 *
 * Attributes:
 *   size    — letter | a4 | legal (default letter)
 *   width / height — explicit CSS lengths, override `size`
 *   margin  — printable inset on every page (default 0.75in)
 *
 * Running header/footer (optional): give an element `slot="header"` or
 * `slot="footer"` and it repeats on every printed page via
 * `position: fixed`. To keep body text from sliding under it, the
 * component prints inside a single-cell table whose <thead>/<tfoot> are
 * spacers sized to the header/footer height — browsers repeat thead/tfoot
 * on every page, so each sheet's content starts below the header and ends
 * above the footer. On screen the header/footer render once at the
 * top/bottom of the sheet.
 *
 * Author content as static HTML so the user can click-to-edit any text
 * directly. Do not set width/padding/background on the document body —
 * the component owns the sheet box.
 */
/* END USAGE */

(() => {
  const PAPER = {
    letter: ['8.5in', '11in'],
    a4: ['210mm', '297mm'],
    legal: ['8.5in', '14in']
  };
  const CSS_LENGTH = /^\d+(\.\d+)?(px|in|mm|cm|pt|pc)$/;
  const safeLen = (v, fb) => CSS_LENGTH.test((v || '').trim()) ? v.trim() : fb;
  const stylesheet = `
    :host {
      position: relative;
      display: block;
      min-height: 100vh;
      background: #ece8dd;
      padding: 48px 24px;
      box-sizing: border-box;
      font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
      --doc-page-w: 8.5in;
      --doc-page-h: 11in;
      --doc-page-margin: 0.75in;
      --doc-hdr-h: 0px;
      --doc-ftr-h: 0px;
    }
    .sheet {
      width: var(--doc-page-w);
      margin: 0 auto;
      background: #fff;
      box-shadow: 0 2px 14px rgba(20, 20, 19, 0.12);
      border-radius: 2px;
      box-sizing: border-box;
      padding: var(--doc-page-margin);
    }
    .frame { width: 100%; border-collapse: collapse; }
    .frame td, .frame th { padding: 0; text-align: left; font-weight: inherit; }
    .hdr-space { height: var(--doc-hdr-h); }
    .ftr-space { height: var(--doc-ftr-h); }
    ::slotted([slot="header"]),
    ::slotted([slot="footer"]) { display: block; box-sizing: border-box; }
    @media print {
      :host { background: none; padding: 0; min-height: 0; }
      .sheet {
        width: auto; margin: 0; box-shadow: none; border-radius: 0;
        padding: 0 var(--doc-page-margin);
      }
      /* The thead/tfoot spacers repeat on every page, so they carry the
       * vertical page margin (which the sheet's own padding cannot, since
       * that padding is consumed once on the first/last page). The running
       * header/footer are fixed inside that band. */
      .hdr-space { height: max(var(--doc-page-margin), calc(var(--doc-hdr-h) + 0.35in)); }
      .ftr-space { height: max(var(--doc-page-margin), calc(var(--doc-ftr-h) + 0.35in)); }
      ::slotted([slot="header"]) {
        position: fixed; top: 0; left: 0; right: 0; margin: 0;
        padding: calc(var(--doc-page-margin) * 0.45) var(--doc-page-margin) 0;
      }
      ::slotted([slot="footer"]) {
        position: fixed; bottom: 0; left: 0; right: 0; margin: 0;
        padding: 0 var(--doc-page-margin) calc(var(--doc-page-margin) * 0.45);
      }
    }
  `;
  class DocPage extends HTMLElement {
    static get observedAttributes() {
      return ['size', 'width', 'height', 'margin'];
    }
    constructor() {
      super();
      this._root = this.attachShadow({
        mode: 'open'
      });
      this._mo = typeof MutationObserver === 'function' ? new MutationObserver(() => this._scheduleMeasure()) : null;
    }
    get pageWidth() {
      const named = PAPER[(this.getAttribute('size') || '').toLowerCase()];
      return safeLen(this.getAttribute('width'), named ? named[0] : PAPER.letter[0]);
    }
    get pageHeight() {
      const named = PAPER[(this.getAttribute('size') || '').toLowerCase()];
      return safeLen(this.getAttribute('height'), named ? named[1] : PAPER.letter[1]);
    }
    get pageMargin() {
      return safeLen(this.getAttribute('margin'), '0.75in');
    }
    connectedCallback() {
      if (!this._sheet) this._render();
      this._syncSize();
      this._syncPrintPageRule();
      this._ensureTextWrapDefaults();
      if (this._mo) this._mo.observe(this, {
        subtree: true,
        childList: true,
        characterData: true,
        attributes: true
      });
      this._onResize = () => this._scheduleMeasure();
      window.addEventListener('resize', this._onResize);
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(() => this._scheduleMeasure());
      }
      this._scheduleMeasure();
    }
    disconnectedCallback() {
      window.removeEventListener('resize', this._onResize);
      if (this._mo) this._mo.disconnect();
      if (this._raf) {
        cancelAnimationFrame(this._raf);
        this._raf = null;
      }
      // Drop the head rules when the last doc-page leaves, so a deleted
      // document's @page geometry and text-wrap defaults can't apply to
      // whatever replaces it.
      if (!document.querySelector('doc-page')) {
        ['doc-page-print', 'doc-page-text-wrap'].forEach(id => {
          const tag = document.getElementById(id);
          if (tag) tag.remove();
        });
      }
    }
    attributeChangedCallback() {
      if (!this._sheet) return;
      this._syncSize();
      this._syncPrintPageRule();
      this._scheduleMeasure();
    }
    _render() {
      this._root.innerHTML = `
        <style>${stylesheet}</style>
        <style id="vars"></style>
        <div class="sheet" data-screen-label="Document">
          <table class="frame" role="presentation">
            <thead><tr><th><div class="hdr-space"><slot name="header"></slot></div></th></tr></thead>
            <tbody><tr><td class="body"><slot></slot></td></tr></tbody>
            <tfoot><tr><td><div class="ftr-space"><slot name="footer"></slot></div></td></tr></tfoot>
          </table>
        </div>`;
      this._sheet = this._root.querySelector('.sheet');
      this._vars = this._root.getElementById('vars');
    }

    /** Runtime sizing lives in a shadow <style> :host rule, never on the
     *  light-DOM host element, so serialize-persist can't write it back. */
    _syncSize(hdrH, ftrH) {
      this._vars.textContent = ':host{' + '--doc-page-w:' + this.pageWidth + ';' + '--doc-page-h:' + this.pageHeight + ';' + '--doc-page-margin:' + this.pageMargin + ';' + '--doc-hdr-h:' + (hdrH || 0) + 'px;' + '--doc-ftr-h:' + (ftrH || 0) + 'px}';
    }

    /** @page is a no-op inside shadow DOM, so the rule lives in <head>.
     *  Re-appended on every sync so it stays last in source order — the
     *  @page cascade is source-order per descriptor, so this rule wins
     *  over any other @page rule in the document. */
    _syncPrintPageRule() {
      const id = 'doc-page-print';
      let tag = document.getElementById(id);
      if (!tag) {
        tag = document.createElement('style');
        tag.id = id;
      }
      document.head.appendChild(tag);
      tag.textContent = '@page { size: ' + this.pageWidth + ' ' + this.pageHeight + '; margin: 0; } ' + '@media print { html, body { margin: 0 !important; padding: 0 !important; background: none !important; height: auto !important; overflow: visible !important; } ' + 'h1,h2,h3,h4,h5,h6 { break-after: avoid; } ' + 'figure,pre,blockquote,img,svg,tr { break-inside: avoid; } ' + 'p,li { orphans: 3; widows: 3; } ' + '* { -webkit-print-color-adjust: exact; print-color-adjust: exact; } ' + '*, *::before, *::after { animation-delay: -99s !important; animation-duration: .001s !important; ' + 'animation-iteration-count: 1 !important; animation-fill-mode: both !important; ' + 'animation-play-state: running !important; transition-duration: 0s !important; } }';
    }

    /** Typographic defaults for document text: balance headings, avoid
     *  widowed/orphaned words in body copy (browsers without text-wrap
     *  support drop the declarations). Zero-specificity via :where() so
     *  any text-wrap authored on those elements wins; document-level so the
     *  rules reach the slotted (light DOM) content — shadow styles can't.
     *  data-omelette-injected marks the tag for the host editor to strip
     *  at serialize, so it is never written back as authored source. */
    _ensureTextWrapDefaults() {
      if (document.getElementById('doc-page-text-wrap')) return;
      const tag = document.createElement('style');
      tag.id = 'doc-page-text-wrap';
      tag.setAttribute('data-omelette-injected', '');
      tag.textContent = ':where(h1,h2,h3,h4,h5,h6){text-wrap:balance}' + ':where(p,li,blockquote,figcaption){text-wrap:pretty}';
      document.head.appendChild(tag);
    }
    _scheduleMeasure() {
      if (this._raf) return;
      this._raf = requestAnimationFrame(() => {
        this._raf = null;
        this._measure();
      });
    }

    /** Slot heights feed the print spacers (--doc-hdr-h / --doc-ftr-h), so
     *  they re-measure on content mutation, resize, and font load. */
    _measure() {
      const hdr = this.querySelector(':scope > [slot="header"]');
      const ftr = this.querySelector(':scope > [slot="footer"]');
      this._syncSize(hdr ? hdr.offsetHeight : 0, ftr ? ftr.offsetHeight : 0);
    }
  }
  if (!customElements.get('doc-page')) {
    customElements.define('doc-page', DocPage);
  }
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "design_handoff_supertrades_terminal/doc-page.js", error: String((e && e.message) || e) }); }

// design_handoff_supertrades_terminal/ui_kits/terminal/data.js
try { (() => {
// SuperTrades terminal — shared fake data + chart helpers
(function () {
  // Deterministic PRNG so charts look identical across loads
  function mulberry32(a) {
    return function () {
      a |= 0;
      a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function genCandles(seed, n, start) {
    const rnd = mulberry32(seed);
    const candles = [];
    let price = start;
    for (let i = 0; i < n; i++) {
      const drift = (rnd() - 0.47) * (start * 0.004);
      const open = price;
      const close = price + drift;
      const high = Math.max(open, close) + rnd() * (start * 0.0018);
      const low = Math.min(open, close) - rnd() * (start * 0.0018);
      const vol = 0.4 + rnd() * 0.6;
      candles.push({
        open,
        close,
        high,
        low,
        vol
      });
      price = close;
    }
    return candles;
  }
  const WATCHLIST = [{
    sym: 'NVDA',
    last: 412.5,
    chg: 2.41,
    vol: '48.2M',
    atr: 4.12,
    conf: 82,
    spread: 0.02
  }, {
    sym: 'SPY',
    last: 598.42,
    chg: 0.42,
    vol: '61.4M',
    atr: 2.85,
    conf: 74,
    spread: 0.01
  }, {
    sym: 'TSLA',
    last: 244.18,
    chg: -0.87,
    vol: '92.1M',
    atr: 6.4,
    conf: 51,
    spread: 0.03
  }, {
    sym: 'AMD',
    last: 162.33,
    chg: 1.12,
    vol: '38.7M',
    atr: 3.05,
    conf: 38,
    spread: 0.02
  }, {
    sym: 'QQQ',
    last: 512.09,
    chg: 0.87,
    vol: '44.9M',
    atr: 3.4,
    conf: 66,
    spread: 0.01
  }, {
    sym: 'META',
    last: 688.71,
    chg: -0.34,
    vol: '12.3M',
    atr: 8.2,
    conf: 45,
    spread: 0.05
  }, {
    sym: 'COIN',
    last: 301.55,
    chg: 3.28,
    vol: '18.8M',
    atr: 11.6,
    conf: 71,
    spread: 0.08
  }, {
    sym: 'MSTR',
    last: 422.9,
    chg: -2.11,
    vol: '9.4M',
    atr: 15.2,
    conf: 29,
    spread: 0.12
  }];
  const SIGNALS = [{
    id: 'SG-8842',
    direction: 'long',
    symbol: 'NVDA',
    strategy: 'Squeeze confluence · 5m',
    entry: '412.50',
    stop: '411.80',
    target: '414.10',
    rr: '1 : 2.3',
    confidence: 82,
    time: '14:32:07',
    live: true,
    thesis: 'Price reclaimed VWAP on rising volume after holding the 411.80 shelf through two tests. Spot pressing the 415 king node from below in a −gamma pocket — dealers chase; 415C 0DTE swept at ask ($2.4M).',
    status: null,
    factors: [{
      label: 'King node 415',
      kind: 'gex',
      fired: true,
      detail: '+1.85B pin above — magnet'
    }, {
      label: 'Squeeze regime',
      kind: 'gex',
      fired: true,
      detail: '−gamma pocket 409–410, dealers chase moves'
    }, {
      label: 'Unusual flow',
      kind: 'flow',
      fired: true,
      detail: '5,100× 415C 0DTE at ask · $2.4M'
    }, {
      label: 'VWAP reclaim',
      kind: 'ta',
      fired: true,
      detail: 'Held 411.80 shelf ×2, reclaimed on volume'
    }, {
      label: 'HVN shelf 411.80',
      kind: 'hvn',
      fired: true,
      detail: 'Stop tucked under high-volume node'
    }, {
      label: 'RVOL 1.8×',
      kind: 'ta',
      fired: true,
      detail: 'Above 1.5× threshold'
    }, {
      label: 'Catalyst clear',
      kind: 'news',
      fired: true,
      detail: 'No earnings 5d · Fed speaker 15:00 — exit before'
    }, {
      label: 'Above gamma flip',
      kind: 'gex',
      fired: true,
      detail: 'Spot 413.11 > flip 409.50'
    }, {
      label: 'Index aligned',
      kind: 'mkt',
      fired: true,
      detail: 'QQQ +0.87% · TICK +412 — tailwind'
    }, {
      label: '14:30–15:00 window',
      kind: 'time',
      fired: true,
      detail: 'A-tier: 0DTE charm flows active'
    }]
  }, {
    id: 'SG-8841',
    direction: 'short',
    symbol: 'TSLA',
    strategy: 'Gamma flip break · 1m',
    entry: '244.60',
    stop: '245.20',
    target: '243.10',
    rr: '1 : 2.5',
    confidence: 71,
    time: '14:27:44',
    live: true,
    thesis: 'Breakout above 245 failed on declining volume as spot lost the 243.80 gamma flip — negative gamma regime opens the range. 240P 0DTE sweeps confirm. Targeting the morning gap fill at 243.10.',
    status: null,
    factors: [{
      label: 'Gamma flip break',
      kind: 'gex',
      fired: true,
      detail: 'Lost 243.80 → −gamma regime'
    }, {
      label: 'Unusual flow',
      kind: 'flow',
      fired: true,
      detail: '6,400× 240P 0DTE at ask · $860K'
    }, {
      label: 'Failed breakout',
      kind: 'ta',
      fired: true,
      detail: '245 push absorbed, lower high'
    }, {
      label: 'LVN below',
      kind: 'hvn',
      fired: true,
      detail: 'Thin volume 243.8→243.1 — fast travel'
    }, {
      label: 'Negative news',
      kind: 'news',
      fired: true,
      detail: 'Deliveries miss headline 14:20'
    }, {
      label: 'King node',
      kind: 'gex',
      fired: false,
      detail: 'No node below until 240 — open air'
    }, {
      label: 'RVOL 2.1×',
      kind: 'ta',
      fired: true,
      detail: 'Expansion volume on the break'
    }, {
      label: 'Index aligned',
      kind: 'mkt',
      fired: true,
      detail: 'Relative weakness vs flat SPY'
    }]
  }, {
    id: 'SG-8840',
    direction: 'long',
    symbol: 'COIN',
    strategy: 'ORB + flow · 5m',
    entry: '299.80',
    stop: '298.40',
    target: '303.20',
    rr: '1 : 2.4',
    confidence: 74,
    time: '14:12:19',
    live: false,
    status: 'Target',
    thesis: 'Opening range breakout continuation with sector momentum and unusual call buying at the lows.',
    factors: [{
      label: 'Unusual flow',
      kind: 'flow',
      fired: true,
      detail: '4,200× 300C 0DTE at ask · $1.9M'
    }, {
      label: 'ORB continuation',
      kind: 'ta',
      fired: true,
      detail: 'Held ORH retest'
    }, {
      label: 'Above gamma flip',
      kind: 'gex',
      fired: true,
      detail: 'Spot > flip 296.50'
    }]
  }, {
    id: 'SG-8839',
    direction: 'long',
    symbol: 'AMD',
    strategy: 'Trend pullback · 15m',
    entry: '161.90',
    stop: '161.20',
    target: '163.50',
    rr: '1 : 2.3',
    confidence: 58,
    time: '13:48:02',
    live: false,
    status: 'Stopped',
    thesis: 'Pullback to rising 20EMA in an uptrend; invalidated on the 161.20 break. TA-only setup — no GEX or flow confirmation.',
    factors: [{
      label: '20EMA pullback',
      kind: 'ta',
      fired: true,
      detail: 'Rising 15m trend'
    }, {
      label: 'GEX support',
      kind: 'gex',
      fired: false,
      detail: 'No node at entry — unprotected'
    }, {
      label: 'Flow confirm',
      kind: 'flow',
      fired: false,
      detail: 'No sweeps — low conviction'
    }, {
      label: 'Index fighting',
      kind: 'mkt',
      fired: false,
      veto: true,
      detail: 'VETO: TICK −4 min streak — should have blocked entry'
    }, {
      label: '13:30–14:00 chop',
      kind: 'time',
      fired: false,
      detail: 'C-tier window — lunch drift'
    }]
  }, {
    id: 'SG-8838',
    direction: 'short',
    symbol: 'META',
    strategy: 'Range fade at call wall · 5m',
    entry: '689.90',
    stop: '691.10',
    target: '686.80',
    rr: '1 : 2.6',
    confidence: 63,
    time: '13:22:37',
    live: false,
    status: 'Filled',
    thesis: 'Fading the top of a three-hour range into the 690 call wall on weakening breadth.',
    factors: [{
      label: 'Call wall 690',
      kind: 'gex',
      fired: true,
      detail: '+gamma cap — dealers sell into it'
    }, {
      label: 'Range top',
      kind: 'ta',
      fired: true,
      detail: 'Third rejection, breadth fading'
    }, {
      label: 'Flow confirm',
      kind: 'flow',
      fired: false,
      detail: 'No put sweeps yet'
    }]
  }];
  const POSITIONS = [{
    sym: 'NVDA',
    side: 'long',
    qty: 200,
    avg: '412.52',
    last: '413.11',
    pnl: 118.0,
    pnlPct: '+0.14%',
    r: '+0.8R'
  }, {
    sym: 'TSLA',
    side: 'short',
    qty: 150,
    avg: '244.58',
    last: '244.21',
    pnl: 55.5,
    pnlPct: '+0.15%',
    r: '+0.6R'
  }];
  const TRADES = [{
    time: '14:12',
    sym: 'COIN',
    side: 'long',
    in: '299.80',
    out: '303.20',
    r: '+2.4R',
    pnl: '+$680.00'
  }, {
    time: '13:48',
    sym: 'AMD',
    side: 'long',
    in: '161.90',
    out: '161.20',
    r: '−1.0R',
    pnl: '−$210.00'
  }, {
    time: '13:22',
    sym: 'META',
    side: 'short',
    in: '689.90',
    out: '687.55',
    r: '+1.9R',
    pnl: '+$470.00'
  }, {
    time: '11:56',
    sym: 'SPY',
    side: 'long',
    in: '596.80',
    out: '598.10',
    r: '+1.6R',
    pnl: '+$390.00'
  }, {
    time: '10:41',
    sym: 'NVDA',
    side: 'short',
    in: '409.90',
    out: '410.60',
    r: '−1.0R',
    pnl: '−$175.00'
  }, {
    time: '09:52',
    sym: 'QQQ',
    side: 'long',
    in: '509.40',
    out: '511.30',
    r: '+2.1R',
    pnl: '+$532.00'
  }];

  // GEX by strike (NVDA) — positive = dealers long gamma (pinning), negative = short gamma (fuel)
  const GEX = {
    symbol: 'NVDA',
    spot: 413.11,
    flip: 409.5,
    kingNode: 415,
    callWall: 420,
    putWall: 405,
    hvl: 412.5,
    strikes: [{
      k: 395,
      gex: -0.42
    }, {
      k: 400,
      gex: -0.88
    }, {
      k: 402.5,
      gex: -0.61
    }, {
      k: 405,
      gex: -1.35
    }, {
      k: 407.5,
      gex: -0.52
    }, {
      k: 409,
      gex: -0.18
    }, {
      k: 410,
      gex: 0.24
    }, {
      k: 412.5,
      gex: 0.96
    }, {
      k: 415,
      gex: 1.85
    }, {
      k: 417.5,
      gex: 0.74
    }, {
      k: 420,
      gex: 1.42
    }, {
      k: 422.5,
      gex: 0.38
    }, {
      k: 425,
      gex: 0.2
    }]
  };
  const GEX_ALERTS = [{
    time: '14:31:52',
    sym: 'NVDA',
    kind: 'squeeze',
    text: 'Short-gamma squeeze setup — spot pressing 415 king node from below, dealers chasing'
  }, {
    time: '14:29:10',
    sym: 'TSLA',
    kind: 'flip',
    text: 'Crossed gamma flip 243.80 → negative gamma regime, expect expanded range'
  }, {
    time: '14:24:36',
    sym: 'SPY',
    kind: 'highvol',
    text: 'HIGH VOL: RVOL 3.2× at 598 node · IV 5m +14%'
  }, {
    time: '14:18:04',
    sym: 'COIN',
    kind: 'unusual',
    text: 'Unusual buying at lows — 4,200× 300C 0DTE swept at ask ($1.9M)'
  }];
  const FLOW = [{
    time: '14:31:44',
    sym: 'NVDA',
    strike: '415C',
    exp: '0DTE',
    side: 'BUY',
    prem: '$2.4M',
    size: '5,100×',
    at: 'ask',
    otm: '0.5%'
  }, {
    time: '14:28:12',
    sym: 'NVDA',
    strike: '420C',
    exp: '2d',
    side: 'BUY',
    prem: '$1.1M',
    size: '3,800×',
    at: 'ask',
    otm: '1.7%'
  }, {
    time: '14:22:51',
    sym: 'TSLA',
    strike: '240P',
    exp: '0DTE',
    side: 'BUY',
    prem: '$860K',
    size: '6,400×',
    at: 'ask',
    otm: '1.8%'
  }, {
    time: '14:18:04',
    sym: 'COIN',
    strike: '300C',
    exp: '0DTE',
    side: 'BUY',
    prem: '$1.9M',
    size: '4,200×',
    at: 'ask',
    otm: '0.6%'
  }, {
    time: '14:11:37',
    sym: 'SPY',
    strike: '600C',
    exp: '1d',
    side: 'SELL',
    prem: '$720K',
    size: '9,000×',
    at: 'bid',
    otm: '0.3%'
  }];

  // Sector universe — 2-3 deepest options books per sector, not just indexes
  const SECTORS = [{
    name: 'Indexes',
    etf: 'SPY',
    regime: '+gamma · pinned',
    chg: 0.42,
    names: [{
      sym: 'SPY',
      last: 598.42,
      chg: 0.42,
      optVol: '8.4M',
      spread: 0.01,
      ivr: 12,
      conv: 61,
      setup: 'Range pin at 600 call wall'
    }, {
      sym: 'QQQ',
      last: 512.09,
      chg: 0.87,
      optVol: '3.9M',
      spread: 0.01,
      ivr: 18,
      conv: 66,
      setup: 'VWAP hold, king node above'
    }]
  }, {
    name: 'Semis',
    etf: 'SMH',
    regime: '−gamma · expansion',
    chg: 1.94,
    names: [{
      sym: 'NVDA',
      last: 412.5,
      chg: 2.41,
      optVol: '2.8M',
      spread: 0.02,
      ivr: 34,
      conv: 82,
      setup: 'Squeeze into 415 king node'
    }, {
      sym: 'AMD',
      last: 162.33,
      chg: 1.12,
      optVol: '840K',
      spread: 0.02,
      ivr: 28,
      conv: 48,
      setup: 'Trend pullback, no flow confirm'
    }, {
      sym: 'AVGO',
      last: 1710.4,
      chg: 1.63,
      optVol: '310K',
      spread: 0.35,
      ivr: 41,
      conv: 55,
      setup: 'ORB hold, wide spreads — size down'
    }]
  }, {
    name: 'Mega-cap',
    etf: 'XLK',
    regime: '+gamma · pinned',
    chg: 0.61,
    names: [{
      sym: 'TSLA',
      last: 244.18,
      chg: -0.87,
      optVol: '2.1M',
      spread: 0.03,
      ivr: 47,
      conv: 71,
      setup: 'Gamma flip break, gap fill below'
    }, {
      sym: 'META',
      last: 688.71,
      chg: -0.34,
      optVol: '620K',
      spread: 0.05,
      ivr: 22,
      conv: 63,
      setup: 'Fade at 690 call wall'
    }, {
      sym: 'AAPL',
      last: 232.66,
      chg: 0.18,
      optVol: '1.4M',
      spread: 0.01,
      ivr: 9,
      conv: 31,
      setup: 'Chop — IV too low, skip'
    }]
  }, {
    name: 'Crypto-linked',
    etf: 'BITO',
    regime: '−gamma · fuel',
    chg: 2.86,
    names: [{
      sym: 'COIN',
      last: 301.55,
      chg: 3.28,
      optVol: '480K',
      spread: 0.08,
      ivr: 58,
      conv: 74,
      setup: 'ORB continuation + call sweeps'
    }, {
      sym: 'MSTR',
      last: 422.9,
      chg: -2.11,
      optVol: '390K',
      spread: 0.12,
      ivr: 66,
      conv: 42,
      setup: 'High IV crush risk — wait'
    }]
  }];

  // Ranked best setups across the universe (conviction = fired factors × weights)
  const BEST_SETUPS = [{
    rank: 1,
    sym: 'NVDA',
    direction: 'long',
    conv: 82,
    fired: '6/6',
    setup: 'Squeeze into 415 king node',
    sector: 'Semis',
    note: '−gamma pocket + $2.4M 0DTE sweeps + VWAP reclaim'
  }, {
    rank: 2,
    sym: 'COIN',
    direction: 'long',
    conv: 74,
    fired: '3/3',
    setup: 'ORB continuation + flow',
    sector: 'Crypto-linked',
    note: 'Sector leading, calls swept at lows'
  }, {
    rank: 3,
    sym: 'TSLA',
    direction: 'short',
    conv: 71,
    fired: '4/5',
    setup: 'Gamma flip break',
    sector: 'Mega-cap',
    note: '−gamma regime opened, open air to 240'
  }];
  const CATALYSTS = [{
    time: '15:00',
    kind: 'macro',
    label: 'Fed speaker (Waller)',
    impact: 'high',
    note: 'Rate-path comments — flatten scalps 5m before'
  }, {
    time: '14:20',
    kind: 'news',
    label: 'TSLA deliveries miss',
    impact: 'high',
    note: 'Headline driving the flip break — confirms short'
  }, {
    time: '13:45',
    kind: 'sector',
    label: 'Semis bid on TSM guidance',
    impact: 'med',
    note: 'SMH leading — tailwind for NVDA long'
  }, {
    time: '10:00',
    kind: 'macro',
    label: 'ISM Services beat',
    impact: 'med',
    note: 'Priced in — no follow-through'
  }, {
    time: 'AMC',
    kind: 'earnings',
    label: 'No earnings in universe today',
    impact: 'low',
    note: 'COIN reports Thu — IV already building'
  }];
  window.ST_DATA = {
    genCandles,
    WATCHLIST,
    SIGNALS,
    POSITIONS,
    TRADES,
    GEX,
    GEX_ALERTS,
    FLOW,
    SECTORS,
    BEST_SETUPS,
    CATALYSTS
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "design_handoff_supertrades_terminal/ui_kits/terminal/data.js", error: String((e && e.message) || e) }); }

// handoff/doc-page.js
try { (() => {
// @ds-adherence-ignore -- omelette starter scaffold (raw elements/hex/px by design)
/* BEGIN USAGE */
/**
 * <doc-page> — paged-document shell for printable HTML.
 *
 * On screen the document renders as a single continuous sheet on a desk
 * background (Google Docs' pageless view): you scroll one tall page card.
 * There is no manual page-splitting — write the whole document as normal
 * flow inside <doc-page> and the browser's print engine paginates it at
 * export.
 *
 * At print the component injects `@page { size: …; margin: 0 }` (which
 * leaves Chrome no margin box to draw its date/URL/page-count header in)
 * and moves the visual margin onto the sheet's own padding, so the printed
 * page has the same inset you see on screen. Standard break-hygiene rules
 * (`break-inside: avoid` on figures, code blocks, images and table rows;
 * `orphans/widows: 3`) are applied so paragraphs and groups split cleanly.
 * On screen and at print, headings default to `text-wrap: balance` and
 * body text (p, li, blockquote, figcaption) to `text-wrap: pretty`, so
 * the document avoids widowed/orphaned words; the defaults have zero
 * specificity, so any text-wrap you declare on those elements wins.
 *
 * Usage:
 *   <style>doc-page:not(:defined){visibility:hidden}</style>
 *   <doc-page size="letter" margin="0.75in">
 *     <h1>Title</h1>
 *     <p>…body…</p>
 *   </doc-page>
 *   <script src="doc-page.js"></script>
 *
 * Attributes:
 *   size    — letter | a4 | legal (default letter)
 *   width / height — explicit CSS lengths, override `size`
 *   margin  — printable inset on every page (default 0.75in)
 *
 * Running header/footer (optional): give an element `slot="header"` or
 * `slot="footer"` and it repeats on every printed page via
 * `position: fixed`. To keep body text from sliding under it, the
 * component prints inside a single-cell table whose <thead>/<tfoot> are
 * spacers sized to the header/footer height — browsers repeat thead/tfoot
 * on every page, so each sheet's content starts below the header and ends
 * above the footer. On screen the header/footer render once at the
 * top/bottom of the sheet.
 *
 * Author content as static HTML so the user can click-to-edit any text
 * directly. Do not set width/padding/background on the document body —
 * the component owns the sheet box.
 */
/* END USAGE */

(() => {
  const PAPER = {
    letter: ['8.5in', '11in'],
    a4: ['210mm', '297mm'],
    legal: ['8.5in', '14in']
  };
  const CSS_LENGTH = /^\d+(\.\d+)?(px|in|mm|cm|pt|pc)$/;
  const safeLen = (v, fb) => CSS_LENGTH.test((v || '').trim()) ? v.trim() : fb;
  const stylesheet = `
    :host {
      position: relative;
      display: block;
      min-height: 100vh;
      background: #ece8dd;
      padding: 48px 24px;
      box-sizing: border-box;
      font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
      --doc-page-w: 8.5in;
      --doc-page-h: 11in;
      --doc-page-margin: 0.75in;
      --doc-hdr-h: 0px;
      --doc-ftr-h: 0px;
    }
    .sheet {
      width: var(--doc-page-w);
      margin: 0 auto;
      background: #fff;
      box-shadow: 0 2px 14px rgba(20, 20, 19, 0.12);
      border-radius: 2px;
      box-sizing: border-box;
      padding: var(--doc-page-margin);
    }
    .frame { width: 100%; border-collapse: collapse; }
    .frame td, .frame th { padding: 0; text-align: left; font-weight: inherit; }
    .hdr-space { height: var(--doc-hdr-h); }
    .ftr-space { height: var(--doc-ftr-h); }
    ::slotted([slot="header"]),
    ::slotted([slot="footer"]) { display: block; box-sizing: border-box; }
    @media print {
      :host { background: none; padding: 0; min-height: 0; }
      .sheet {
        width: auto; margin: 0; box-shadow: none; border-radius: 0;
        padding: 0 var(--doc-page-margin);
      }
      /* The thead/tfoot spacers repeat on every page, so they carry the
       * vertical page margin (which the sheet's own padding cannot, since
       * that padding is consumed once on the first/last page). The running
       * header/footer are fixed inside that band. */
      .hdr-space { height: max(var(--doc-page-margin), calc(var(--doc-hdr-h) + 0.35in)); }
      .ftr-space { height: max(var(--doc-page-margin), calc(var(--doc-ftr-h) + 0.35in)); }
      ::slotted([slot="header"]) {
        position: fixed; top: 0; left: 0; right: 0; margin: 0;
        padding: calc(var(--doc-page-margin) * 0.45) var(--doc-page-margin) 0;
      }
      ::slotted([slot="footer"]) {
        position: fixed; bottom: 0; left: 0; right: 0; margin: 0;
        padding: 0 var(--doc-page-margin) calc(var(--doc-page-margin) * 0.45);
      }
    }
  `;
  class DocPage extends HTMLElement {
    static get observedAttributes() {
      return ['size', 'width', 'height', 'margin'];
    }
    constructor() {
      super();
      this._root = this.attachShadow({
        mode: 'open'
      });
      this._mo = typeof MutationObserver === 'function' ? new MutationObserver(() => this._scheduleMeasure()) : null;
    }
    get pageWidth() {
      const named = PAPER[(this.getAttribute('size') || '').toLowerCase()];
      return safeLen(this.getAttribute('width'), named ? named[0] : PAPER.letter[0]);
    }
    get pageHeight() {
      const named = PAPER[(this.getAttribute('size') || '').toLowerCase()];
      return safeLen(this.getAttribute('height'), named ? named[1] : PAPER.letter[1]);
    }
    get pageMargin() {
      return safeLen(this.getAttribute('margin'), '0.75in');
    }
    connectedCallback() {
      if (!this._sheet) this._render();
      this._syncSize();
      this._syncPrintPageRule();
      this._ensureTextWrapDefaults();
      if (this._mo) this._mo.observe(this, {
        subtree: true,
        childList: true,
        characterData: true,
        attributes: true
      });
      this._onResize = () => this._scheduleMeasure();
      window.addEventListener('resize', this._onResize);
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(() => this._scheduleMeasure());
      }
      this._scheduleMeasure();
    }
    disconnectedCallback() {
      window.removeEventListener('resize', this._onResize);
      if (this._mo) this._mo.disconnect();
      if (this._raf) {
        cancelAnimationFrame(this._raf);
        this._raf = null;
      }
      // Drop the head rules when the last doc-page leaves, so a deleted
      // document's @page geometry and text-wrap defaults can't apply to
      // whatever replaces it.
      if (!document.querySelector('doc-page')) {
        ['doc-page-print', 'doc-page-text-wrap'].forEach(id => {
          const tag = document.getElementById(id);
          if (tag) tag.remove();
        });
      }
    }
    attributeChangedCallback() {
      if (!this._sheet) return;
      this._syncSize();
      this._syncPrintPageRule();
      this._scheduleMeasure();
    }
    _render() {
      this._root.innerHTML = `
        <style>${stylesheet}</style>
        <style id="vars"></style>
        <div class="sheet" data-screen-label="Document">
          <table class="frame" role="presentation">
            <thead><tr><th><div class="hdr-space"><slot name="header"></slot></div></th></tr></thead>
            <tbody><tr><td class="body"><slot></slot></td></tr></tbody>
            <tfoot><tr><td><div class="ftr-space"><slot name="footer"></slot></div></td></tr></tfoot>
          </table>
        </div>`;
      this._sheet = this._root.querySelector('.sheet');
      this._vars = this._root.getElementById('vars');
    }

    /** Runtime sizing lives in a shadow <style> :host rule, never on the
     *  light-DOM host element, so serialize-persist can't write it back. */
    _syncSize(hdrH, ftrH) {
      this._vars.textContent = ':host{' + '--doc-page-w:' + this.pageWidth + ';' + '--doc-page-h:' + this.pageHeight + ';' + '--doc-page-margin:' + this.pageMargin + ';' + '--doc-hdr-h:' + (hdrH || 0) + 'px;' + '--doc-ftr-h:' + (ftrH || 0) + 'px}';
    }

    /** @page is a no-op inside shadow DOM, so the rule lives in <head>.
     *  Re-appended on every sync so it stays last in source order — the
     *  @page cascade is source-order per descriptor, so this rule wins
     *  over any other @page rule in the document. */
    _syncPrintPageRule() {
      const id = 'doc-page-print';
      let tag = document.getElementById(id);
      if (!tag) {
        tag = document.createElement('style');
        tag.id = id;
      }
      document.head.appendChild(tag);
      tag.textContent = '@page { size: ' + this.pageWidth + ' ' + this.pageHeight + '; margin: 0; } ' + '@media print { html, body { margin: 0 !important; padding: 0 !important; background: none !important; height: auto !important; overflow: visible !important; } ' + 'h1,h2,h3,h4,h5,h6 { break-after: avoid; } ' + 'figure,pre,blockquote,img,svg,tr { break-inside: avoid; } ' + 'p,li { orphans: 3; widows: 3; } ' + '* { -webkit-print-color-adjust: exact; print-color-adjust: exact; } ' + '*, *::before, *::after { animation-delay: -99s !important; animation-duration: .001s !important; ' + 'animation-iteration-count: 1 !important; animation-fill-mode: both !important; ' + 'animation-play-state: running !important; transition-duration: 0s !important; } }';
    }

    /** Typographic defaults for document text: balance headings, avoid
     *  widowed/orphaned words in body copy (browsers without text-wrap
     *  support drop the declarations). Zero-specificity via :where() so
     *  any text-wrap authored on those elements wins; document-level so the
     *  rules reach the slotted (light DOM) content — shadow styles can't.
     *  data-omelette-injected marks the tag for the host editor to strip
     *  at serialize, so it is never written back as authored source. */
    _ensureTextWrapDefaults() {
      if (document.getElementById('doc-page-text-wrap')) return;
      const tag = document.createElement('style');
      tag.id = 'doc-page-text-wrap';
      tag.setAttribute('data-omelette-injected', '');
      tag.textContent = ':where(h1,h2,h3,h4,h5,h6){text-wrap:balance}' + ':where(p,li,blockquote,figcaption){text-wrap:pretty}';
      document.head.appendChild(tag);
    }
    _scheduleMeasure() {
      if (this._raf) return;
      this._raf = requestAnimationFrame(() => {
        this._raf = null;
        this._measure();
      });
    }

    /** Slot heights feed the print spacers (--doc-hdr-h / --doc-ftr-h), so
     *  they re-measure on content mutation, resize, and font load. */
    _measure() {
      const hdr = this.querySelector(':scope > [slot="header"]');
      const ftr = this.querySelector(':scope > [slot="footer"]');
      this._syncSize(hdr ? hdr.offsetHeight : 0, ftr ? ftr.offsetHeight : 0);
    }
  }
  if (!customElements.get('doc-page')) {
    customElements.define('doc-page', DocPage);
  }
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "handoff/doc-page.js", error: String((e && e.message) || e) }); }

// ui_kits/mobile/ios-frame.jsx
try { (() => {
// @ds-adherence-ignore -- omelette starter scaffold (raw elements/hex/px by design)

/* BEGIN USAGE */
// iOS.jsx — Simplified iOS 26 (Liquid Glass) device frame
// Based on the iOS 26 UI Kit + Figma status bar spec. No assets, no deps.
// Exports (to window): IOSDevice, IOSStatusBar, IOSNavBar, IOSGlassPill, IOSList, IOSListRow, IOSKeyboard
//
// Usage — wrap your screen content in <IOSDevice> to get the bezel, status bar
// and home indicator (props: title, dark, keyboard):
//
//   <IOSDevice title="Settings">
//     ...your screen content...
//   </IOSDevice>
//   <IOSDevice dark title="Search" keyboard>…</IOSDevice>
/* END USAGE */

// ─────────────────────────────────────────────────────────────
// Status bar
// ─────────────────────────────────────────────────────────────
function IOSStatusBar({
  dark = false,
  time = '9:41'
}) {
  const c = dark ? '#fff' : '#000';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 154,
      alignItems: 'center',
      justifyContent: 'center',
      padding: '21px 24px 19px',
      boxSizing: 'border-box',
      position: 'relative',
      zIndex: 20,
      width: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      height: 22,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      paddingTop: 1.5
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: '-apple-system, "SF Pro", system-ui',
      fontWeight: 590,
      fontSize: 17,
      lineHeight: '22px',
      color: c
    }
  }, time)), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      height: 22,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 7,
      paddingTop: 1,
      paddingRight: 1
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "19",
    height: "12",
    viewBox: "0 0 19 12"
  }, /*#__PURE__*/React.createElement("rect", {
    x: "0",
    y: "7.5",
    width: "3.2",
    height: "4.5",
    rx: "0.7",
    fill: c
  }), /*#__PURE__*/React.createElement("rect", {
    x: "4.8",
    y: "5",
    width: "3.2",
    height: "7",
    rx: "0.7",
    fill: c
  }), /*#__PURE__*/React.createElement("rect", {
    x: "9.6",
    y: "2.5",
    width: "3.2",
    height: "9.5",
    rx: "0.7",
    fill: c
  }), /*#__PURE__*/React.createElement("rect", {
    x: "14.4",
    y: "0",
    width: "3.2",
    height: "12",
    rx: "0.7",
    fill: c
  })), /*#__PURE__*/React.createElement("svg", {
    width: "17",
    height: "12",
    viewBox: "0 0 17 12"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M8.5 3.2C10.8 3.2 12.9 4.1 14.4 5.6L15.5 4.5C13.7 2.7 11.2 1.5 8.5 1.5C5.8 1.5 3.3 2.7 1.5 4.5L2.6 5.6C4.1 4.1 6.2 3.2 8.5 3.2Z",
    fill: c
  }), /*#__PURE__*/React.createElement("path", {
    d: "M8.5 6.8C9.9 6.8 11.1 7.3 12 8.2L13.1 7.1C11.8 5.9 10.2 5.1 8.5 5.1C6.8 5.1 5.2 5.9 3.9 7.1L5 8.2C5.9 7.3 7.1 6.8 8.5 6.8Z",
    fill: c
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "8.5",
    cy: "10.5",
    r: "1.5",
    fill: c
  })), /*#__PURE__*/React.createElement("svg", {
    width: "27",
    height: "13",
    viewBox: "0 0 27 13"
  }, /*#__PURE__*/React.createElement("rect", {
    x: "0.5",
    y: "0.5",
    width: "23",
    height: "12",
    rx: "3.5",
    stroke: c,
    strokeOpacity: "0.35",
    fill: "none"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "2",
    y: "2",
    width: "20",
    height: "9",
    rx: "2",
    fill: c
  }), /*#__PURE__*/React.createElement("path", {
    d: "M25 4.5V8.5C25.8 8.2 26.5 7.2 26.5 6.5C26.5 5.8 25.8 4.8 25 4.5Z",
    fill: c,
    fillOpacity: "0.4"
  }))));
}

// ─────────────────────────────────────────────────────────────
// Liquid glass pill — blur + tint + shine
// ─────────────────────────────────────────────────────────────
function IOSGlassPill({
  children,
  dark = false,
  style = {}
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      height: 44,
      minWidth: 44,
      borderRadius: 9999,
      position: 'relative',
      overflow: 'hidden',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: dark ? '0 2px 6px rgba(0,0,0,0.35), 0 6px 16px rgba(0,0,0,0.2)' : '0 1px 3px rgba(0,0,0,0.07), 0 3px 10px rgba(0,0,0,0.06)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      borderRadius: 9999,
      backdropFilter: 'blur(12px) saturate(180%)',
      WebkitBackdropFilter: 'blur(12px) saturate(180%)',
      background: dark ? 'rgba(120,120,128,0.28)' : 'rgba(255,255,255,0.5)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      borderRadius: 9999,
      boxShadow: dark ? 'inset 1.5px 1.5px 1px rgba(255,255,255,0.15), inset -1px -1px 1px rgba(255,255,255,0.08)' : 'inset 1.5px 1.5px 1px rgba(255,255,255,0.7), inset -1px -1px 1px rgba(255,255,255,0.4)',
      border: dark ? '0.5px solid rgba(255,255,255,0.15)' : '0.5px solid rgba(0,0,0,0.06)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      zIndex: 1,
      display: 'flex',
      alignItems: 'center',
      padding: '0 4px'
    }
  }, children));
}

// ─────────────────────────────────────────────────────────────
// Navigation bar — glass pills + large title
// ─────────────────────────────────────────────────────────────
function IOSNavBar({
  title = 'Title',
  dark = false,
  trailingIcon = true
}) {
  const muted = dark ? 'rgba(255,255,255,0.6)' : '#404040';
  const text = dark ? '#fff' : '#000';
  const pillIcon = content => /*#__PURE__*/React.createElement(IOSGlassPill, {
    dark: dark
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 36,
      height: 36,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, content));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      paddingTop: 62,
      paddingBottom: 10,
      position: 'relative',
      zIndex: 5
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 16px'
    }
  }, pillIcon(/*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "20",
    viewBox: "0 0 12 20",
    fill: "none",
    style: {
      marginLeft: -1
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "M10 2L2 10l8 8",
    stroke: muted,
    strokeWidth: "2.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }))), trailingIcon && pillIcon(/*#__PURE__*/React.createElement("svg", {
    width: "22",
    height: "6",
    viewBox: "0 0 22 6"
  }, /*#__PURE__*/React.createElement("circle", {
    cx: "3",
    cy: "3",
    r: "2.5",
    fill: muted
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "11",
    cy: "3",
    r: "2.5",
    fill: muted
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "19",
    cy: "3",
    r: "2.5",
    fill: muted
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '0 16px',
      fontFamily: '-apple-system, system-ui',
      fontSize: 34,
      fontWeight: 700,
      lineHeight: '41px',
      color: text,
      letterSpacing: 0.4
    }
  }, title));
}

// ─────────────────────────────────────────────────────────────
// Grouped list (inset card, r:26) + row (52px)
// ─────────────────────────────────────────────────────────────
function IOSListRow({
  title,
  detail,
  icon,
  chevron = true,
  isLast = false,
  dark = false
}) {
  const text = dark ? '#fff' : '#000';
  const sec = dark ? 'rgba(235,235,245,0.6)' : 'rgba(60,60,67,0.6)';
  const ter = dark ? 'rgba(235,235,245,0.3)' : 'rgba(60,60,67,0.3)';
  const sep = dark ? 'rgba(84,84,88,0.65)' : 'rgba(60,60,67,0.12)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      minHeight: 52,
      padding: '0 16px',
      position: 'relative',
      fontFamily: '-apple-system, system-ui',
      fontSize: 17,
      letterSpacing: -0.43
    }
  }, icon && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 30,
      height: 30,
      borderRadius: 7,
      background: icon,
      marginRight: 12,
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      color: text
    }
  }, title), detail && /*#__PURE__*/React.createElement("span", {
    style: {
      color: sec,
      marginRight: 6
    }
  }, detail), chevron && /*#__PURE__*/React.createElement("svg", {
    width: "8",
    height: "14",
    viewBox: "0 0 8 14",
    style: {
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "M1 1l6 6-6 6",
    stroke: ter,
    strokeWidth: "2",
    fill: "none",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  })), !isLast && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      bottom: 0,
      right: 0,
      left: icon ? 58 : 16,
      height: 0.5,
      background: sep
    }
  }));
}
function IOSList({
  header,
  children,
  dark = false
}) {
  const hc = dark ? 'rgba(235,235,245,0.6)' : 'rgba(60,60,67,0.6)';
  const bg = dark ? '#1C1C1E' : '#fff';
  return /*#__PURE__*/React.createElement("div", null, header && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: '-apple-system, system-ui',
      fontSize: 13,
      color: hc,
      textTransform: 'uppercase',
      padding: '8px 36px 6px',
      letterSpacing: -0.08
    }
  }, header), /*#__PURE__*/React.createElement("div", {
    style: {
      background: bg,
      borderRadius: 26,
      margin: '0 16px',
      overflow: 'hidden'
    }
  }, children));
}

// ─────────────────────────────────────────────────────────────
// Device frame
// ─────────────────────────────────────────────────────────────
function IOSDevice({
  children,
  width = 402,
  height = 874,
  dark = false,
  title,
  keyboard = false
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width,
      height,
      borderRadius: 48,
      overflow: 'hidden',
      position: 'relative',
      background: dark ? '#000' : '#F2F2F7',
      boxShadow: '0 40px 80px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.12)',
      fontFamily: '-apple-system, system-ui, sans-serif',
      WebkitFontSmoothing: 'antialiased'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 11,
      left: '50%',
      transform: 'translateX(-50%)',
      width: 126,
      height: 37,
      borderRadius: 24,
      background: '#000',
      zIndex: 50
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      zIndex: 10
    }
  }, /*#__PURE__*/React.createElement(IOSStatusBar, {
    dark: dark
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      display: 'flex',
      flexDirection: 'column'
    }
  }, title !== undefined && /*#__PURE__*/React.createElement(IOSNavBar, {
    title: title,
    dark: dark
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflow: 'auto'
    }
  }, children), keyboard && /*#__PURE__*/React.createElement(IOSKeyboard, {
    dark: dark
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      bottom: 0,
      left: 0,
      right: 0,
      zIndex: 60,
      height: 34,
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'flex-end',
      paddingBottom: 8,
      pointerEvents: 'none'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 139,
      height: 5,
      borderRadius: 100,
      background: dark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.25)'
    }
  })));
}

// ─────────────────────────────────────────────────────────────
// Keyboard — iOS 26 liquid glass
// ─────────────────────────────────────────────────────────────
function IOSKeyboard({
  dark = false
}) {
  const glyph = dark ? 'rgba(255,255,255,0.7)' : '#595959';
  const sugg = dark ? 'rgba(255,255,255,0.6)' : '#333';
  const keyBg = dark ? 'rgba(255,255,255,0.22)' : 'rgba(255,255,255,0.85)';

  // special-key icons
  const icons = {
    shift: /*#__PURE__*/React.createElement("svg", {
      width: "19",
      height: "17",
      viewBox: "0 0 19 17"
    }, /*#__PURE__*/React.createElement("path", {
      d: "M9.5 1L1 9.5h4.5V16h8V9.5H18L9.5 1z",
      fill: glyph
    })),
    del: /*#__PURE__*/React.createElement("svg", {
      width: "23",
      height: "17",
      viewBox: "0 0 23 17"
    }, /*#__PURE__*/React.createElement("path", {
      d: "M7 1h13a2 2 0 012 2v11a2 2 0 01-2 2H7l-6-7.5L7 1z",
      fill: "none",
      stroke: glyph,
      strokeWidth: "1.6",
      strokeLinejoin: "round"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M10 5l7 7M17 5l-7 7",
      stroke: glyph,
      strokeWidth: "1.6",
      strokeLinecap: "round"
    })),
    ret: /*#__PURE__*/React.createElement("svg", {
      width: "20",
      height: "14",
      viewBox: "0 0 20 14"
    }, /*#__PURE__*/React.createElement("path", {
      d: "M18 1v6H4m0 0l4-4M4 7l4 4",
      fill: "none",
      stroke: "#fff",
      strokeWidth: "1.8",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }))
  };
  const key = (content, {
    w,
    flex,
    ret,
    fs = 25,
    k
  } = {}) => /*#__PURE__*/React.createElement("div", {
    key: k,
    style: {
      height: 42,
      borderRadius: 8.5,
      flex: flex ? 1 : undefined,
      width: w,
      minWidth: 0,
      background: ret ? '#08f' : keyBg,
      boxShadow: '0 1px 0 rgba(0,0,0,0.075)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: '-apple-system, "SF Compact", system-ui',
      fontSize: fs,
      fontWeight: 458,
      color: ret ? '#fff' : glyph
    }
  }, content);
  const row = (keys, pad = 0) => /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6.5,
      justifyContent: 'center',
      padding: `0 ${pad}px`
    }
  }, keys.map(l => key(l, {
    flex: true,
    k: l
  })));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      zIndex: 15,
      borderRadius: 27,
      overflow: 'hidden',
      padding: '11px 0 2px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      boxShadow: dark ? '0 -2px 20px rgba(0,0,0,0.09)' : '0 -1px 6px rgba(0,0,0,0.018), 0 -3px 20px rgba(0,0,0,0.012)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      borderRadius: 27,
      backdropFilter: 'blur(12px) saturate(180%)',
      WebkitBackdropFilter: 'blur(12px) saturate(180%)',
      background: dark ? 'rgba(120,120,128,0.14)' : 'rgba(255,255,255,0.25)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      borderRadius: 27,
      boxShadow: dark ? 'inset 1.5px 1.5px 1px rgba(255,255,255,0.15)' : 'inset 1.5px 1.5px 1px rgba(255,255,255,0.7), inset -1px -1px 1px rgba(255,255,255,0.4)',
      border: dark ? '0.5px solid rgba(255,255,255,0.15)' : '0.5px solid rgba(0,0,0,0.06)',
      pointerEvents: 'none'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 20,
      alignItems: 'center',
      padding: '8px 22px 13px',
      width: '100%',
      boxSizing: 'border-box',
      position: 'relative'
    }
  }, ['"The"', 'the', 'to'].map((w, i) => /*#__PURE__*/React.createElement(React.Fragment, {
    key: i
  }, i > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 1,
      height: 25,
      background: '#ccc',
      opacity: 0.3
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      textAlign: 'center',
      fontFamily: '-apple-system, system-ui',
      fontSize: 17,
      color: sugg,
      letterSpacing: -0.43,
      lineHeight: '22px'
    }
  }, w)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 13,
      padding: '0 6.5px',
      width: '100%',
      boxSizing: 'border-box',
      position: 'relative'
    }
  }, row(['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p']), row(['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'], 20), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 14.25,
      alignItems: 'center'
    }
  }, key(icons.shift, {
    w: 45,
    k: 'shift'
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6.5,
      flex: 1
    }
  }, ['z', 'x', 'c', 'v', 'b', 'n', 'm'].map(l => key(l, {
    flex: true,
    k: l
  }))), key(icons.del, {
    w: 45,
    k: 'del'
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      alignItems: 'center'
    }
  }, key('ABC', {
    w: 92.25,
    fs: 18,
    k: 'abc'
  }), key('', {
    flex: true,
    k: 'space'
  }), key(icons.ret, {
    w: 92.25,
    ret: true,
    k: 'ret'
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 56,
      width: '100%',
      position: 'relative'
    }
  }));
}
Object.assign(window, {
  IOSDevice,
  IOSStatusBar,
  IOSNavBar,
  IOSGlassPill,
  IOSList,
  IOSListRow,
  IOSKeyboard
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/mobile/ios-frame.jsx", error: String((e && e.message) || e) }); }

// ui_kits/mobile/screens.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// SuperTrades mobile — screens (rendered inside a 390pt phone shell)
const {
  SignalCard: MbSignal,
  Badge: MbBadge,
  StatCard: MbStat,
  TickerChip: MbChip,
  Switch: MbSwitch,
  Button: MbButton,
  ConfidenceMeter: MbConf,
  Tabs: MbTabs
} = window.SuperTradesDesignSystem_4b8c0b;
function MobileHeader({
  title,
  right
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '14px 16px 10px'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: '700 20px/1.1 var(--font-sans)'
    }
  }, title), right);
}
function MobileSignals({
  onOpen
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      padding: '0 12px 12px'
    }
  }, /*#__PURE__*/React.createElement(MobileHeader, {
    title: "Signals",
    right: /*#__PURE__*/React.createElement(MbBadge, {
      tone: "long",
      dot: true,
      pulse: true
    }, "2 live")
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      overflow: 'auto',
      padding: '0 4px'
    }
  }, /*#__PURE__*/React.createElement(MbChip, {
    symbol: "SPY",
    change: 0.42,
    size: "sm"
  }), /*#__PURE__*/React.createElement(MbChip, {
    symbol: "QQQ",
    change: 0.87,
    size: "sm"
  }), /*#__PURE__*/React.createElement(MbChip, {
    symbol: "VIX",
    change: -3.1,
    size: "sm"
  })), window.ST_DATA.SIGNALS.slice(0, 3).map(s => /*#__PURE__*/React.createElement(MbSignal, _extends({
    key: s.id
  }, s, {
    style: {
      width: 'auto'
    },
    onClick: () => onOpen(s)
  }))));
}
function MobileWatchlist() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      padding: '0 12px 12px'
    }
  }, /*#__PURE__*/React.createElement(MobileHeader, {
    title: "Watchlist"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden'
    }
  }, window.ST_DATA.WATCHLIST.slice(0, 7).map((r, i) => /*#__PURE__*/React.createElement("div", {
    key: r.sym,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '12px 14px',
      minHeight: 44,
      borderBottom: i < 6 ? '1px solid var(--border-hairline)' : 'none'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)'
    }
  }, r.sym), /*#__PURE__*/React.createElement(MbConf, {
    value: r.conf,
    compact: true,
    style: {
      marginLeft: 4
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      font: 'var(--type-data)',
      fontVariantNumeric: 'tabular-nums'
    }
  }, r.last.toFixed(2)), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data)',
      width: 76,
      textAlign: 'right',
      color: r.chg >= 0 ? 'var(--green-500)' : 'var(--red-500)',
      fontVariantNumeric: 'tabular-nums'
    }
  }, r.chg >= 0 ? '▲ +' : '▼ −', Math.abs(r.chg).toFixed(2), "%")))));
}
function MobilePnl() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      padding: '0 12px 12px'
    }
  }, /*#__PURE__*/React.createElement(MobileHeader, {
    title: "P&L",
    right: /*#__PURE__*/React.createElement("span", {
      style: {
        font: 'var(--type-data-sm)',
        color: 'var(--text-muted)'
      }
    }, "14:32 ET")
  }), /*#__PURE__*/React.createElement(MbStat, {
    label: "Session P&L",
    value: "+$1,284.50",
    delta: "+2.4%",
    spark: [2, 4, 3, 5, 4, 7, 6, 9, 8, 11]
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(MbStat, {
    label: "Win rate",
    value: "68%",
    size: "sm",
    style: {
      flex: 1,
      minWidth: 0
    }
  }), /*#__PURE__*/React.createElement(MbStat, {
    label: "Trades",
    value: "6",
    size: "sm",
    style: {
      flex: 1,
      minWidth: 0
    }
  }), /*#__PURE__*/React.createElement(MbStat, {
    label: "Avg R",
    value: "+1.4R",
    size: "sm",
    style: {
      flex: 1,
      minWidth: 0
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden'
    }
  }, window.ST_DATA.TRADES.slice(0, 5).map((t, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '12px 14px',
      minHeight: 44,
      borderBottom: i < 4 ? '1px solid var(--border-hairline)' : 'none'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, t.time), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)'
    }
  }, t.sym), /*#__PURE__*/React.createElement(MbBadge, {
    tone: t.side === 'long' ? 'long' : 'short'
  }, t.side), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      font: 'var(--type-data)',
      color: t.pnl.startsWith('+') ? 'var(--green-500)' : 'var(--red-500)',
      fontVariantNumeric: 'tabular-nums'
    }
  }, t.pnl)))));
}
function MobileDetail({
  signal,
  onBack
}) {
  const s = signal || window.ST_DATA.SIGNALS[0];
  const isLong = s.direction === 'long';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      padding: '0 12px 12px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '14px 4px 0'
    }
  }, /*#__PURE__*/React.createElement(MbButton, {
    variant: "ghost",
    size: "sm",
    onClick: onBack
  }, "\u2039 Back"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)',
      fontSize: 17
    }
  }, s.symbol), /*#__PURE__*/React.createElement(MbBadge, {
    tone: isLong ? 'long' : 'short',
    dot: s.live,
    pulse: s.live
  }, isLong ? '▲ Long' : '▼ Short'), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, s.time)), /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: `1px solid ${isLong ? 'var(--green-line)' : 'var(--red-line)'}`,
      borderRadius: 'var(--radius-md)',
      padding: 16,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      boxShadow: s.live ? `var(--shadow-card), ${isLong ? 'var(--glow-green)' : 'var(--glow-red)'}` : 'var(--shadow-card)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between'
    }
  }, [['Entry', s.entry, isLong ? 'var(--green-500)' : 'var(--red-500)'], ['Stop', s.stop, 'var(--red-500)'], ['Target', s.target, 'var(--cyan-500)']].map(([l, v, c]) => /*#__PURE__*/React.createElement("div", {
    key: l,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)'
    }
  }, l), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-lg)',
      color: c,
      fontVariantNumeric: 'tabular-nums'
    }
  }, v)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingTop: 10,
      borderTop: '1px solid var(--border-hairline)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data)',
      color: 'var(--text-secondary)'
    }
  }, "R:R ", s.rr), /*#__PURE__*/React.createElement(MbConf, {
    value: s.confidence,
    compact: true
  }))), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body)',
      color: 'var(--text-secondary)',
      padding: '0 4px'
    }
  }, s.thesis), /*#__PURE__*/React.createElement(MbButton, {
    variant: isLong ? 'long' : 'short',
    size: "lg",
    fullWidth: true,
    icon: /*#__PURE__*/React.createElement("span", null, isLong ? '▲' : '▼')
  }, isLong ? 'Long' : 'Short', " ", s.symbol), /*#__PURE__*/React.createElement(MbButton, {
    variant: "secondary",
    size: "lg",
    fullWidth: true
  }, "Set alert"));
}
function MobileSettings() {
  const [a, setA] = React.useState({
    push: true,
    sound: true,
    stops: true
  });
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      padding: '0 12px 12px'
    }
  }, /*#__PURE__*/React.createElement(MobileHeader, {
    title: "Alerts"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-md)',
      padding: '4px 14px'
    }
  }, [['push', 'Push notifications'], ['sound', 'Sound on new signal'], ['stops', 'Alert on stop hit']].map(([k, label], i) => /*#__PURE__*/React.createElement("div", {
    key: k,
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      minHeight: 48,
      borderBottom: i < 2 ? '1px solid var(--border-hairline)' : 'none'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body)'
    }
  }, label), /*#__PURE__*/React.createElement(MbSwitch, {
    checked: a[k],
    onChange: v => setA(p => ({
      ...p,
      [k]: v
    }))
  })))));
}
Object.assign(window, {
  MobileSignals,
  MobileWatchlist,
  MobilePnl,
  MobileDetail,
  MobileSettings
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/mobile/screens.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/ChartView.jsx
try { (() => {
// Screen: chart + trade analysis
const {
  Tabs: ChTabs,
  Badge: ChBadge,
  Button: ChButton,
  DataTable: ChTable,
  Card: ChCard
} = window.SuperTradesDesignSystem_4b8c0b;
function ChartView() {
  const [tf, setTf] = React.useState('5m');
  const candles = React.useMemo(() => window.ST_DATA.genCandles(42 + tf.length, 72, 411.2), [tf]);
  const levels = [{
    price: 412.5,
    label: 'ENTRY',
    color: 'var(--green-500)'
  }, {
    price: 411.8,
    label: 'STOP',
    color: 'var(--red-500)'
  }, {
    price: 414.1,
    label: 'TGT',
    color: 'var(--cyan-500)'
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      display: 'flex',
      gap: 12,
      height: '100%',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)',
      fontSize: 18
    }
  }, "NVDA"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-lg)',
      color: 'var(--green-500)'
    }
  }, "413.11 \u25B2 +2.41%"), /*#__PURE__*/React.createElement(ChBadge, {
    tone: "long",
    dot: true,
    pulse: true
  }, "Long active"), /*#__PURE__*/React.createElement("a", {
    href: "https://www.tradingview.com/chart/?symbol=NASDAQ%3ANVDA",
    target: "_blank",
    rel: "noopener",
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '5px 10px',
      borderRadius: 'var(--radius-sm)',
      border: '1px solid var(--border-default)',
      font: '600 12px/1 var(--font-sans)',
      color: 'var(--text-secondary)',
      whiteSpace: 'nowrap'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "external-link",
    size: 13
  }), " TradingView"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto'
    }
  }, /*#__PURE__*/React.createElement(ChTabs, {
    tabs: ['1m', '5m', '15m', '1h'],
    active: tf,
    onChange: setTf,
    size: "sm"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement(CandleChart, {
    candles: candles,
    height: 380,
    levels: levels
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 16,
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, /*#__PURE__*/React.createElement("span", null, "VWAP 411.94"), /*#__PURE__*/React.createElement("span", null, "ATR(14) 4.12"), /*#__PURE__*/React.createElement("span", null, "RVOL 1.8\xD7"), /*#__PURE__*/React.createElement("span", null, "Spread 0.02"), /*#__PURE__*/React.createElement("span", null, "Vol 48.2M"))), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 320,
      flexShrink: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement(ChCard, {
    title: "Trade analysis",
    meta: "SG-8842"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      font: 'var(--type-body)',
      color: 'var(--text-secondary)'
    }
  }, /*#__PURE__*/React.createElement("span", null, "Price reclaimed VWAP on rising volume after holding the 411.80 shelf through two tests. Tape shows aggressive buyers above 412.40."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: '8px 12px',
      fontVariantNumeric: 'tabular-nums'
    }
  }, [['Entry', '412.50', 'var(--green-500)'], ['Stop', '411.80', 'var(--red-500)'], ['Target', '414.10', 'var(--cyan-500)'], ['R:R', '1 : 2.3', 'var(--text-primary)']].map(([l, v, c]) => /*#__PURE__*/React.createElement("div", {
    key: l,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)'
    }
  }, l), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-lg)',
      color: c
    }
  }, v)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(ChButton, {
    variant: "long",
    fullWidth: true,
    icon: /*#__PURE__*/React.createElement("span", null, "\u25B2")
  }, "Add"), /*#__PURE__*/React.createElement(ChButton, {
    variant: "secondary",
    fullWidth: true
  }, "Scale out"), /*#__PURE__*/React.createElement(ChButton, {
    variant: "danger",
    fullWidth: true
  }, "Close")))), /*#__PURE__*/React.createElement(ChCard, {
    title: "Time & sales",
    meta: "live"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
      font: 'var(--type-data-sm)',
      fontVariantNumeric: 'tabular-nums'
    }
  }, [['14:32:07', '413.11', '400', 'var(--green-500)'], ['14:32:06', '413.09', '1,200', 'var(--green-500)'], ['14:32:05', '413.05', '250', 'var(--red-500)'], ['14:32:05', '413.08', '800', 'var(--green-500)'], ['14:32:04', '413.02', '2,100', 'var(--red-500)'], ['14:32:03', '413.04', '600', 'var(--green-500)'], ['14:32:02', '412.99', '150', 'var(--red-500)']].map((t, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-muted)'
    }
  }, t[0]), /*#__PURE__*/React.createElement("span", {
    style: {
      color: t[3]
    }
  }, t[1]), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-secondary)'
    }
  }, t[2])))))));
}
window.ChartView = ChartView;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/ChartView.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/GexView.jsx
try { (() => {
// Screen: GEX — gamma exposure profile, key nodes, squeeze alerts, unusual flow
const {
  Badge: GxBadge,
  Card: GxCard,
  Tabs: GxTabs,
  DataTable: GxTable
} = window.SuperTradesDesignSystem_4b8c0b;

// Horizontal GEX-by-strike profile: green bars = +gamma (pinning), red = −gamma (fuel)
function GexProfile({
  gex
}) {
  const maxAbs = Math.max(...gex.strikes.map(s => Math.abs(s.gex)));
  const rows = [...gex.strikes].sort((a, b) => b.k - a.k);
  const half = 50; // % of width per side
  const markers = [{
    k: gex.kingNode,
    label: 'KING',
    color: 'var(--green-400)'
  }, {
    k: gex.callWall,
    label: 'CALL WALL',
    color: 'var(--cyan-500)'
  }, {
    k: gex.putWall,
    label: 'PUT WALL',
    color: 'var(--red-400)'
  }, {
    k: gex.hvl,
    label: 'HVL',
    color: 'var(--amber-500)'
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
      background: 'var(--surface-inset)',
      borderRadius: 'var(--radius-sm)',
      padding: '12px 12px 8px'
    }
  }, rows.map(s => {
    const pos = s.gex >= 0;
    const w = Math.abs(s.gex) / maxAbs * half;
    const isKing = s.k === gex.kingNode;
    const marker = markers.find(m => m.k === s.k);
    const belowFlip = s.k <= gex.flip;
    return /*#__PURE__*/React.createElement("div", {
      key: s.k,
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        height: 20
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 44,
        textAlign: 'right',
        font: 'var(--type-data-sm)',
        color: isKing ? 'var(--green-400)' : marker ? marker.color : 'var(--text-muted)',
        fontWeight: isKing || marker ? 700 : 500
      }
    }, s.k), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        position: 'relative',
        height: 12
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'absolute',
        left: '50%',
        top: -4,
        bottom: -4,
        width: 1,
        background: 'var(--border-default)'
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'absolute',
        top: 0,
        height: 12,
        borderRadius: 2,
        left: pos ? '50%' : `${50 - w}%`,
        width: `${w}%`,
        background: pos ? 'var(--green-500)' : 'var(--red-500)',
        opacity: isKing ? 1 : 0.45 + Math.abs(s.gex) / maxAbs * 0.4,
        boxShadow: isKing ? 'var(--glow-green-strong)' : 'none'
      }
    })), /*#__PURE__*/React.createElement("span", {
      style: {
        width: 52,
        font: 'var(--type-data-sm)',
        color: pos ? 'var(--green-500)' : 'var(--red-500)',
        textAlign: 'right'
      }
    }, pos ? '+' : '−', Math.abs(s.gex).toFixed(2), "B"), /*#__PURE__*/React.createElement("span", {
      style: {
        width: 78,
        font: '700 9px/1 var(--font-mono)',
        letterSpacing: '0.06em',
        color: marker ? marker.color : belowFlip ? 'var(--text-disabled)' : 'transparent',
        whiteSpace: 'nowrap'
      }
    }, marker ? marker.label : ''));
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 16,
      paddingTop: 8,
      marginTop: 4,
      borderTop: '1px solid var(--border-hairline)',
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--green-500)'
    }
  }, "\u25A0"), " +gamma \xB7 pinning"), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--red-500)'
    }
  }, "\u25A0"), " \u2212gamma \xB7 fuel"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto'
    }
  }, "spot ", gex.spot.toFixed(2), " \xB7 flip ", gex.flip.toFixed(2))));
}
const GX_ALERT_TONES = {
  squeeze: 'long',
  flip: 'warning',
  highvol: 'warning',
  unusual: 'info'
};
const GX_ALERT_LABELS = {
  squeeze: 'Squeeze',
  flip: 'Gamma flip',
  highvol: 'High vol',
  unusual: 'Unusual flow'
};
function GexView() {
  const {
    GEX,
    GEX_ALERTS,
    FLOW
  } = window.ST_DATA;
  const regime = GEX.spot > GEX.flip;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      display: 'flex',
      gap: 12,
      height: '100%',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1.2,
      minWidth: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-display)',
      fontSize: 24
    }
  }, "GEX"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)',
      fontSize: 16
    }
  }, GEX.symbol), /*#__PURE__*/React.createElement(GxBadge, {
    tone: regime ? 'long' : 'short',
    dot: true,
    pulse: true
  }, regime ? '+gamma regime' : '−gamma regime'), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, "net GEX +$2.1B \xB7 updated 14:32:07")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10
    }
  }, [['King node', GEX.kingNode, 'var(--green-400)'], ['Gamma flip', GEX.flip, 'var(--amber-500)'], ['Call wall', GEX.callWall, 'var(--cyan-500)'], ['Put wall', GEX.putWall, 'var(--red-400)'], ['HVL', GEX.hvl, 'var(--amber-500)']].map(([l, v, c]) => /*#__PURE__*/React.createElement("div", {
    key: l,
    style: {
      flex: 1,
      background: 'var(--surface-card)',
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-card)',
      padding: 12,
      display: 'flex',
      flexDirection: 'column',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)',
      whiteSpace: 'nowrap'
    }
  }, l), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-lg)',
      color: c,
      fontVariantNumeric: 'tabular-nums'
    }
  }, Number(v).toFixed(2))))), /*#__PURE__*/React.createElement(GexProfile, {
    gex: GEX
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 380,
      flexShrink: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement(GxCard, {
    title: "Alerts",
    meta: "live"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10
    }
  }, GEX_ALERTS.map((a, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
      paddingBottom: 10,
      borderBottom: i < GEX_ALERTS.length - 1 ? '1px solid var(--border-hairline)' : 'none'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(GxBadge, {
    tone: GX_ALERT_TONES[a.kind]
  }, GX_ALERT_LABELS[a.kind]), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)'
    }
  }, a.sym), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, a.time)), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-caption)',
      color: 'var(--text-secondary)'
    }
  }, a.text))))), /*#__PURE__*/React.createElement(GxCard, {
    title: "Unusual flow",
    meta: "swept at ask/bid"
  }, /*#__PURE__*/React.createElement(GxTable, {
    dense: true,
    columns: [{
      key: 'time',
      label: 'Time',
      render: v => /*#__PURE__*/React.createElement("span", {
        style: {
          color: 'var(--text-muted)'
        }
      }, v.slice(0, 5))
    }, {
      key: 'sym',
      label: 'Tkr',
      render: v => /*#__PURE__*/React.createElement("span", {
        style: {
          font: 'var(--type-ticker)'
        }
      }, v)
    }, {
      key: 'strike',
      label: 'Strike',
      render: (v, r) => /*#__PURE__*/React.createElement("span", {
        style: {
          color: v.endsWith('C') ? 'var(--green-500)' : 'var(--red-500)'
        }
      }, v, " ", /*#__PURE__*/React.createElement("span", {
        style: {
          color: 'var(--text-muted)'
        }
      }, r.exp))
    }, {
      key: 'size',
      label: 'Size',
      align: 'right'
    }, {
      key: 'prem',
      label: 'Prem',
      align: 'right',
      render: (v, r) => /*#__PURE__*/React.createElement("span", {
        style: {
          color: r.side === 'BUY' ? 'var(--green-500)' : 'var(--red-500)'
        }
      }, v)
    }],
    rows: FLOW
  }))));
}
window.GexView = GexView;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/GexView.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/Portfolio.jsx
try { (() => {
// Screen: positions & P&L dashboard
const {
  StatCard: PfStat,
  DataTable: PfTable,
  Card: PfCard,
  Badge: PfBadge,
  Button: PfButton
} = window.SuperTradesDesignSystem_4b8c0b;
function Portfolio() {
  const {
    POSITIONS,
    TRADES
  } = window.ST_DATA;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      height: '100%',
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-display)',
      fontSize: 24
    }
  }, "Positions & P&L"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(PfStat, {
    label: "Session P&L",
    value: "+$1,284.50",
    delta: "+2.4%",
    spark: [2, 4, 3, 5, 4, 7, 6, 9, 8, 11],
    style: {
      flex: 1.4
    }
  }), /*#__PURE__*/React.createElement(PfStat, {
    label: "Realized",
    value: "+$1,111.00",
    size: "sm",
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(PfStat, {
    label: "Unrealized",
    value: "+$173.50",
    size: "sm",
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(PfStat, {
    label: "Win rate",
    value: "68%",
    delta: "+4%",
    size: "sm",
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(PfStat, {
    label: "Trades",
    value: "6",
    size: "sm",
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(PfStat, {
    label: "Max drawdown",
    value: "\u2212$385.00",
    deltaTone: "down",
    size: "sm",
    style: {
      flex: 1
    }
  })), /*#__PURE__*/React.createElement(PfCard, {
    title: "Open positions",
    meta: "2 open \xB7 risk $460"
  }, /*#__PURE__*/React.createElement(PfTable, {
    dense: true,
    columns: [{
      key: 'sym',
      label: 'Ticker',
      render: (v, r) => /*#__PURE__*/React.createElement("span", {
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          gap: 8
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          font: 'var(--type-ticker)'
        }
      }, v), /*#__PURE__*/React.createElement(PfBadge, {
        tone: r.side === 'long' ? 'long' : 'short'
      }, r.side))
    }, {
      key: 'qty',
      label: 'Qty',
      align: 'right'
    }, {
      key: 'avg',
      label: 'Avg',
      align: 'right'
    }, {
      key: 'last',
      label: 'Last',
      align: 'right'
    }, {
      key: 'pnl',
      label: 'P&L $',
      align: 'right',
      render: v => /*#__PURE__*/React.createElement("span", {
        style: {
          color: v >= 0 ? 'var(--green-500)' : 'var(--red-500)'
        }
      }, v >= 0 ? '+' : '−', "$", Math.abs(v).toFixed(2))
    }, {
      key: 'r',
      label: 'R',
      align: 'right',
      render: v => /*#__PURE__*/React.createElement("span", {
        style: {
          color: v.startsWith('+') ? 'var(--green-500)' : 'var(--red-500)'
        }
      }, v)
    }, {
      key: 'act',
      label: '',
      align: 'right',
      render: (_, r) => /*#__PURE__*/React.createElement(PfButton, {
        variant: "danger",
        size: "sm"
      }, "Close")
    }],
    rows: POSITIONS
  })), /*#__PURE__*/React.createElement(PfCard, {
    title: "Today's trades",
    meta: "closed \xB7 6"
  }, /*#__PURE__*/React.createElement(PfTable, {
    dense: true,
    columns: [{
      key: 'time',
      label: 'Time'
    }, {
      key: 'sym',
      label: 'Ticker',
      render: v => /*#__PURE__*/React.createElement("span", {
        style: {
          font: 'var(--type-ticker)'
        }
      }, v)
    }, {
      key: 'side',
      label: 'Side',
      render: v => /*#__PURE__*/React.createElement(PfBadge, {
        tone: v === 'long' ? 'long' : 'short'
      }, v)
    }, {
      key: 'in',
      label: 'Entry',
      align: 'right'
    }, {
      key: 'out',
      label: 'Exit',
      align: 'right'
    }, {
      key: 'r',
      label: 'R',
      align: 'right',
      render: v => /*#__PURE__*/React.createElement("span", {
        style: {
          color: v.startsWith('+') ? 'var(--green-500)' : 'var(--red-500)'
        }
      }, v)
    }, {
      key: 'pnl',
      label: 'P&L',
      align: 'right',
      render: v => /*#__PURE__*/React.createElement("span", {
        style: {
          color: v.startsWith('+') ? 'var(--green-500)' : 'var(--red-500)'
        }
      }, v)
    }],
    rows: TRADES
  })));
}
window.Portfolio = Portfolio;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/Portfolio.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/Scanner.jsx
try { (() => {
// Screen: watchlist / scanner — sector-tiered universe + ranked best setups
const {
  ConfidenceMeter: ScConf,
  Badge: ScBadge,
  Input: ScInput,
  Select: ScSelect
} = window.SuperTradesDesignSystem_4b8c0b;
function ScTh({
  children,
  align
}) {
  return /*#__PURE__*/React.createElement("th", {
    style: {
      textAlign: align || 'left',
      padding: '7px 12px',
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)',
      borderBottom: '1px solid var(--border-default)',
      whiteSpace: 'nowrap'
    }
  }, children);
}
function ScTd({
  children,
  align,
  style
}) {
  return /*#__PURE__*/React.createElement("td", {
    style: {
      textAlign: align || 'left',
      padding: '9px 12px',
      font: 'var(--type-data)',
      color: 'var(--text-primary)',
      borderBottom: '1px solid var(--border-hairline)',
      fontVariantNumeric: 'tabular-nums',
      whiteSpace: 'nowrap',
      ...style
    }
  }, children);
}
function SectorBlock({
  sector,
  onOpenChart
}) {
  const [hover, setHover] = React.useState(-1);
  const negGamma = sector.regime.startsWith('−');
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-card)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '10px 12px',
      background: 'var(--bg-2)',
      borderBottom: '1px solid var(--border-hairline)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-heading)'
    }
  }, sector.name), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)',
      color: 'var(--text-muted)'
    }
  }, sector.etf), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data)',
      color: sector.chg >= 0 ? 'var(--green-500)' : 'var(--red-500)'
    }
  }, sector.chg >= 0 ? '▲ +' : '▼ −', Math.abs(sector.chg).toFixed(2), "%"), /*#__PURE__*/React.createElement(ScBadge, {
    tone: negGamma ? 'short' : 'neutral',
    style: {
      marginLeft: 'auto'
    }
  }, sector.regime)), /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse'
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement(ScTh, null, "Ticker"), /*#__PURE__*/React.createElement(ScTh, {
    align: "right"
  }, "Last"), /*#__PURE__*/React.createElement(ScTh, {
    align: "right"
  }, "Chg %"), /*#__PURE__*/React.createElement(ScTh, {
    align: "right"
  }, "Opt vol"), /*#__PURE__*/React.createElement(ScTh, {
    align: "right"
  }, "Spread"), /*#__PURE__*/React.createElement(ScTh, {
    align: "right"
  }, "IV rank"), /*#__PURE__*/React.createElement(ScTh, {
    align: "right"
  }, "Conviction"), /*#__PURE__*/React.createElement(ScTh, null, "Setup"))), /*#__PURE__*/React.createElement("tbody", null, sector.names.map((r, i) => /*#__PURE__*/React.createElement("tr", {
    key: r.sym,
    onClick: () => onOpenChart && onOpenChart(),
    onMouseEnter: () => setHover(i),
    onMouseLeave: () => setHover(-1),
    style: {
      background: hover === i ? 'var(--surface-raised)' : 'transparent',
      cursor: 'pointer',
      transition: 'background var(--duration-fast) var(--ease-out)'
    }
  }, /*#__PURE__*/React.createElement(ScTd, {
    style: {
      font: 'var(--type-ticker)'
    }
  }, r.sym), /*#__PURE__*/React.createElement(ScTd, {
    align: "right"
  }, r.last.toFixed(2)), /*#__PURE__*/React.createElement(ScTd, {
    align: "right",
    style: {
      color: r.chg >= 0 ? 'var(--green-500)' : 'var(--red-500)'
    }
  }, r.chg >= 0 ? '+' : '−', Math.abs(r.chg).toFixed(2), "%"), /*#__PURE__*/React.createElement(ScTd, {
    align: "right"
  }, r.optVol), /*#__PURE__*/React.createElement(ScTd, {
    align: "right",
    style: {
      color: r.spread > 0.05 ? 'var(--amber-500)' : undefined
    }
  }, r.spread.toFixed(2)), /*#__PURE__*/React.createElement(ScTd, {
    align: "right",
    style: {
      color: r.ivr >= 50 ? 'var(--amber-500)' : undefined
    }
  }, r.ivr), /*#__PURE__*/React.createElement(ScTd, {
    align: "right"
  }, /*#__PURE__*/React.createElement(ScConf, {
    value: r.conv,
    compact: true
  })), /*#__PURE__*/React.createElement(ScTd, {
    style: {
      font: 'var(--type-caption)',
      color: 'var(--text-secondary)',
      whiteSpace: 'normal'
    }
  }, r.setup))))));
}
function BestSetups({
  onOpenChart
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--green-line)',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-card), var(--glow-green)',
      padding: 14,
      display: 'flex',
      flexDirection: 'column',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-heading)'
    }
  }, "Best setups"), /*#__PURE__*/React.createElement(ScBadge, {
    tone: "long",
    dot: true,
    pulse: true
  }, "ranked"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, "whole universe \xB7 14:32")), window.ST_DATA.BEST_SETUPS.map(b => /*#__PURE__*/React.createElement("div", {
    key: b.rank,
    onClick: () => onOpenChart && onOpenChart(),
    style: {
      display: 'flex',
      gap: 12,
      alignItems: 'center',
      padding: '10px 12px',
      background: 'var(--surface-inset)',
      border: '1px solid var(--border-hairline)',
      borderRadius: 'var(--radius-sm)',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: '700 18px/1 var(--font-mono)',
      color: b.rank === 1 ? 'var(--green-400)' : 'var(--text-muted)',
      width: 22,
      textAlign: 'center'
    }
  }, b.rank), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 3,
      minWidth: 0,
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)'
    }
  }, b.sym), /*#__PURE__*/React.createElement(ScBadge, {
    tone: b.direction === 'long' ? 'long' : 'short'
  }, b.direction === 'long' ? '▲ Long' : '▼ Short'), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, b.sector)), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-strong)',
      fontSize: 13
    }
  }, b.setup), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-caption)',
      color: 'var(--text-secondary)'
    }
  }, b.note)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'flex-end',
      gap: 4,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement(ScConf, {
    value: b.conv,
    compact: true
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)',
      whiteSpace: 'nowrap'
    }
  }, b.fired, " factors")))));
}
function Scanner({
  onOpenChart
}) {
  const sectors = window.ST_DATA.SECTORS;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      display: 'flex',
      gap: 12,
      height: '100%',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1.4,
      minWidth: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-display)',
      fontSize: 24,
      marginRight: 'auto'
    }
  }, "Scanner"), /*#__PURE__*/React.createElement(ScSelect, {
    label: "Universe",
    options: ['Liquid options only', 'All'],
    defaultValue: "Liquid options only",
    size: "sm",
    style: {
      width: 170
    }
  }), /*#__PURE__*/React.createElement(ScSelect, {
    label: "Sort",
    options: ['Conviction', 'Options volume', 'IV rank'],
    defaultValue: "Conviction",
    size: "sm",
    style: {
      width: 150
    }
  })), sectors.map(s => /*#__PURE__*/React.createElement(SectorBlock, {
    key: s.name,
    sector: s,
    onOpenChart: onOpenChart
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-caption)',
      color: 'var(--text-muted)'
    }
  }, "Universe is capped to names with deep options books \u2014 opt vol, spread and IV rank shown per name. Spread > 0.05 and IV rank \u2265 50 flagged amber.")), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 400,
      flexShrink: 0,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement(BestSetups, {
    onOpenChart: onOpenChart
  })));
}
window.Scanner = Scanner;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/Scanner.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/Settings.jsx
try { (() => {
// Screen: alerts & settings
const {
  Card: SetCard,
  Switch: SetSwitch,
  Input: SetInput,
  Select: SetSelect,
  Button: SetButton,
  Badge: SetBadge
} = window.SuperTradesDesignSystem_4b8c0b;
function Settings() {
  const [alerts, setAlerts] = React.useState({
    push: true,
    sound: true,
    email: false,
    stops: true,
    targets: true,
    spread: false
  });
  const set = k => v => setAlerts(a => ({
    ...a,
    [k]: v
  }));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      height: '100%',
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-display)',
      fontSize: 24
    }
  }, "Alerts & Settings"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 12,
      maxWidth: 860,
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement(SetCard, {
    title: "Signal alerts"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement(SetSwitch, {
    checked: alerts.push,
    onChange: set('push'),
    label: "Push notifications"
  }), /*#__PURE__*/React.createElement(SetSwitch, {
    checked: alerts.sound,
    onChange: set('sound'),
    label: "Sound on new signal"
  }), /*#__PURE__*/React.createElement(SetSwitch, {
    checked: alerts.email,
    onChange: set('email'),
    label: "Email digest (end of session)"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: '1px solid var(--border-hairline)',
      paddingTop: 14,
      display: 'flex',
      flexDirection: 'column',
      gap: 14
    }
  }, /*#__PURE__*/React.createElement(SetSwitch, {
    checked: alerts.stops,
    onChange: set('stops'),
    label: "Alert on stop hit"
  }), /*#__PURE__*/React.createElement(SetSwitch, {
    checked: alerts.targets,
    onChange: set('targets'),
    label: "Alert on target reached"
  }), /*#__PURE__*/React.createElement(SetSwitch, {
    checked: alerts.spread,
    onChange: set('spread'),
    label: "Warn on spread widening"
  })), /*#__PURE__*/React.createElement(SetSelect, {
    label: "Minimum confidence to alert",
    options: ['Any', '45 · MED', '70 · HIGH'],
    defaultValue: "45 \xB7 MED"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(SetCard, {
    title: "Risk defaults",
    meta: "applies to sizing math"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(SetInput, {
    label: "Max risk per trade",
    prefix: "$",
    mono: true,
    defaultValue: "250.00"
  }), /*#__PURE__*/React.createElement(SetInput, {
    label: "Daily loss limit",
    prefix: "$",
    mono: true,
    defaultValue: "750.00"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(SetSelect, {
    label: "Default timeframe",
    options: ['1m', '5m', '15m'],
    defaultValue: "5m",
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(SetSelect, {
    label: "Session",
    options: ['RTH only', 'Include pre-market'],
    defaultValue: "RTH only",
    style: {
      flex: 1
    }
  })), /*#__PURE__*/React.createElement(SetButton, {
    variant: "primary",
    style: {
      alignSelf: 'flex-start'
    }
  }, "Save defaults"))), /*#__PURE__*/React.createElement(SetCard, {
    title: "Account",
    meta: "Pro plan"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 32,
      height: 32,
      borderRadius: '50%',
      background: 'var(--surface-raised)',
      border: '1px solid var(--border-default)',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      font: '600 12px var(--font-mono)',
      color: 'var(--green-400)'
    }
  }, "JD"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-strong)'
    }
  }, "J. Doe"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, "jd@example.com")), /*#__PURE__*/React.createElement(SetBadge, {
    tone: "long",
    style: {
      marginLeft: 'auto'
    }
  }, "Pro"))))));
}
window.SettingsScreen = Settings;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/Settings.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/SignalDetail.jsx
try { (() => {
// Screen: signal detail (entry/stop/target breakdown)
const {
  Badge: SdBadge,
  Button: SdButton,
  Card: SdCard,
  ConfidenceMeter: SdConf
} = window.SuperTradesDesignSystem_4b8c0b;
function SignalDetail({
  signal,
  onBack
}) {
  const s = signal || window.ST_DATA.SIGNALS[0];
  const isLong = s.direction === 'long';
  const dirColor = isLong ? 'var(--green-500)' : 'var(--red-500)';
  const candles = React.useMemo(() => window.ST_DATA.genCandles(7, 56, parseFloat(s.entry) * 0.997), [s.id]);
  const levels = [{
    price: parseFloat(s.entry),
    label: 'ENTRY',
    color: 'var(--green-500)'
  }, {
    price: parseFloat(s.stop),
    label: 'STOP',
    color: 'var(--red-500)'
  }, {
    price: parseFloat(s.target),
    label: 'TGT',
    color: 'var(--cyan-500)'
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      height: '100%',
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(SdButton, {
    variant: "ghost",
    size: "sm",
    onClick: onBack,
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-left",
      size: 14
    })
  }, "Signals"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-ticker)',
      fontSize: 20
    }
  }, s.symbol), /*#__PURE__*/React.createElement(SdBadge, {
    tone: isLong ? 'long' : 'short',
    dot: s.live,
    pulse: s.live
  }, isLong ? '▲ Long' : '▼ Short'), s.status && /*#__PURE__*/React.createElement(SdBadge, {
    tone: "neutral"
  }, s.status), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, s.id, " \xB7 ", s.time, " ET"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 'auto',
      font: 'var(--type-caption)',
      color: 'var(--text-secondary)'
    }
  }, s.strategy)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 12,
      flex: 1,
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minHeight: 260
    }
  }, /*#__PURE__*/React.createElement(CandleChart, {
    candles: candles,
    height: 340,
    levels: levels
  })), /*#__PURE__*/React.createElement(SdCard, {
    title: "Conviction stack",
    meta: s.factors ? `${s.factors.filter(f => f.fired).length}/${s.factors.length} fired` : ''
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10
    }
  }, (s.factors || []).map((f, i) => {
    const isVeto = f.veto && !f.fired;
    return /*#__PURE__*/React.createElement("div", {
      key: f.label,
      style: {
        display: 'flex',
        gap: 10,
        alignItems: 'flex-start'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 18,
        height: 18,
        borderRadius: '50%',
        flexShrink: 0,
        marginTop: 1,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: isVeto ? 'var(--red-dim)' : f.fired ? 'var(--green-dim)' : 'var(--surface-inset)',
        border: `1px solid ${isVeto ? 'var(--red-line)' : f.fired ? 'var(--green-line)' : 'var(--border-default)'}`,
        color: isVeto ? 'var(--red-500)' : f.fired ? 'var(--green-500)' : 'var(--text-disabled)',
        fontSize: 10,
        fontWeight: 700
      }
    }, isVeto ? '✕' : f.fired ? '✓' : '○'), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'flex',
        gap: 6,
        alignItems: 'baseline'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        font: '700 9px/1 var(--font-mono)',
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: isVeto ? 'var(--red-400)' : f.fired ? 'var(--text-muted)' : 'var(--text-disabled)'
      }
    }, f.kind), /*#__PURE__*/React.createElement("span", {
      style: {
        font: 'var(--type-body-strong)',
        fontSize: 13,
        color: isVeto ? 'var(--red-400)' : f.fired ? 'var(--text-primary)' : 'var(--text-disabled)'
      }
    }, f.label)), f.detail && /*#__PURE__*/React.createElement("span", {
      style: {
        font: 'var(--type-caption)',
        color: isVeto ? 'var(--red-400)' : f.fired ? 'var(--text-secondary)' : 'var(--text-disabled)'
      }
    }, f.detail)));
  }))), /*#__PURE__*/React.createElement(SdCard, {
    title: "Thesis"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body)',
      color: 'var(--text-secondary)'
    }
  }, s.thesis))), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 300,
      flexShrink: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(SdCard, {
    live: s.live,
    direction: s.direction
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 14
    }
  }, [['Entry', s.entry, dirColor], ['Stop', s.stop, 'var(--red-500)'], ['Target', s.target, 'var(--cyan-500)']].map(([l, v, c]) => /*#__PURE__*/React.createElement("div", {
    key: l,
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)'
    }
  }, l), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-lg)',
      color: c,
      fontVariantNumeric: 'tabular-nums'
    }
  }, v))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      paddingTop: 10,
      borderTop: '1px solid var(--border-hairline)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)'
    }
  }, "R:R"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-lg)'
    }
  }, s.rr)), /*#__PURE__*/React.createElement("div", {
    style: {
      alignSelf: 'center'
    }
  }, /*#__PURE__*/React.createElement(SdConf, {
    value: s.confidence
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(SdButton, {
    variant: isLong ? 'long' : 'short',
    fullWidth: true,
    icon: /*#__PURE__*/React.createElement("span", null, isLong ? '▲' : '▼')
  }, isLong ? 'Long' : 'Short', " ", s.symbol), /*#__PURE__*/React.createElement(SdButton, {
    variant: "secondary",
    fullWidth: true
  }, "Set alert")))), /*#__PURE__*/React.createElement(SdCard, {
    title: "Risk math",
    meta: "$250 max risk"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      font: 'var(--type-data)',
      color: 'var(--text-secondary)',
      fontVariantNumeric: 'tabular-nums'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("span", null, "Risk / share"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-primary)'
    }
  }, Math.abs(parseFloat(s.entry) - parseFloat(s.stop)).toFixed(2))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("span", null, "Size @ $250 risk"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-primary)'
    }
  }, Math.floor(250 / Math.abs(parseFloat(s.entry) - parseFloat(s.stop))), " sh")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("span", null, "Reward @ target"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--green-500)'
    }
  }, "+$", (Math.floor(250 / Math.abs(parseFloat(s.entry) - parseFloat(s.stop))) * Math.abs(parseFloat(s.target) - parseFloat(s.entry))).toFixed(0))))))));
}
window.SignalDetail = SignalDetail;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/SignalDetail.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/SignalsFeed.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// Screen: live signal feed
const {
  SignalCard: STSignalCard,
  Badge: STBadge,
  Tabs: STTabs,
  StatCard: STStatCard,
  Card: STCard
} = window.SuperTradesDesignSystem_4b8c0b;
const ST_CAT_TONES = {
  macro: 'warning',
  news: 'short',
  sector: 'long',
  earnings: 'info'
};
function CatalystRail() {
  return /*#__PURE__*/React.createElement(STCard, {
    title: "Catalysts",
    meta: "today",
    style: {
      width: 300,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10
    }
  }, window.ST_DATA.CATALYSTS.map((c, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 3,
      paddingBottom: 10,
      borderBottom: i < window.ST_DATA.CATALYSTS.length - 1 ? '1px solid var(--border-hairline)' : 'none'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)',
      width: 38
    }
  }, c.time), /*#__PURE__*/React.createElement(STBadge, {
    tone: ST_CAT_TONES[c.kind] || 'neutral'
  }, c.kind), c.impact === 'high' && /*#__PURE__*/React.createElement("span", {
    style: {
      font: '700 9px/1 var(--font-mono)',
      letterSpacing: '0.06em',
      color: 'var(--amber-500)'
    }
  }, "HIGH IMPACT")), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-strong)',
      fontSize: 13
    }
  }, c.label), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-caption)',
      color: 'var(--text-secondary)'
    }
  }, c.note)))));
}
function SignalsFeed({
  onOpenSignal
}) {
  const [filter, setFilter] = React.useState('all');
  const signals = window.ST_DATA.SIGNALS.filter(s => filter === 'all' ? true : filter === 'live' ? s.live : s.direction === filter);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      display: 'flex',
      gap: 12,
      height: '100%',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-display)',
      fontSize: 24
    }
  }, "Live Signals"), /*#__PURE__*/React.createElement(STBadge, {
    tone: "long",
    dot: true,
    pulse: true
  }, "2 active"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto'
    }
  }, /*#__PURE__*/React.createElement(STTabs, {
    size: "sm",
    active: filter,
    onChange: setFilter,
    tabs: [{
      id: 'all',
      label: 'All'
    }, {
      id: 'live',
      label: 'Live'
    }, {
      id: 'long',
      label: 'Longs'
    }, {
      id: 'short',
      label: 'Shorts'
    }]
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(STStatCard, {
    label: "Signals today",
    value: "18",
    size: "sm",
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(STStatCard, {
    label: "Hit rate",
    value: "72%",
    delta: "+4%",
    size: "sm",
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(STStatCard, {
    label: "Avg R",
    value: "+1.4R",
    size: "sm",
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(STStatCard, {
    label: "Avg hold",
    value: "6m 12s",
    size: "sm",
    style: {
      flex: 1
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))',
      gap: 12,
      alignItems: 'start'
    }
  }, signals.map(s => /*#__PURE__*/React.createElement(STSignalCard, _extends({
    key: s.id
  }, s, {
    style: {
      width: 'auto'
    },
    onClick: () => onOpenSignal(s)
  }))))), /*#__PURE__*/React.createElement("div", {
    style: {
      flexShrink: 0,
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement(CatalystRail, null)));
}
window.SignalsFeed = SignalsFeed;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/SignalsFeed.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/chrome.jsx
try { (() => {
// SuperTrades terminal — shell chrome: TopBar, SideRail, CandleChart
const {
  Badge,
  TickerChip,
  Button
} = window.SuperTradesDesignSystem_4b8c0b;

// Lucide icon rendered from the loaded UMD icon data (window.lucide)
function Icon({
  name,
  size = 16,
  color = 'currentColor',
  strokeWidth = 1.5,
  style
}) {
  const pascal = name.split('-').map(s => s[0].toUpperCase() + s.slice(1)).join('');
  const node = window.lucide && window.lucide.icons && (window.lucide.icons[pascal] || window.lucide.icons[name]);
  if (!node) return /*#__PURE__*/React.createElement("span", {
    style: {
      width: size,
      height: size,
      display: 'inline-block'
    }
  });
  // lucide UMD icon data: ["svg", attrs, [[tag, attrs, children?], …]] — render only the children
  const renderNode = (n, i) => {
    const [tag, attrs, kids] = n;
    return React.createElement(tag, {
      key: i,
      ...attrs
    }, (kids || []).map(renderNode));
  };
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: color,
    strokeWidth: strokeWidth,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      flexShrink: 0,
      ...style
    }
  }, (node[2] || []).map(renderNode));
}
function Wordmark() {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      font: '700 16px/1 var(--font-sans)',
      letterSpacing: '0.02em',
      color: 'var(--text-primary)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--green-500)'
    }
  }, "SUPER"), "TRADES");
}
function TopBar() {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      height: 'var(--topbar-height)',
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      padding: '0 16px',
      background: 'var(--bg-0)',
      borderBottom: '1px solid var(--border-hairline)',
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement(Wordmark, null), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      marginLeft: 12
    }
  }, /*#__PURE__*/React.createElement(TickerChip, {
    symbol: "SPY",
    price: "598.42",
    change: 0.42,
    size: "sm"
  }), /*#__PURE__*/React.createElement(TickerChip, {
    symbol: "QQQ",
    price: "512.09",
    change: 0.87,
    size: "sm"
  }), /*#__PURE__*/React.createElement(TickerChip, {
    symbol: "VIX",
    price: "14.22",
    change: -3.1,
    size: "sm"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 14,
      alignItems: 'center',
      paddingLeft: 14,
      borderLeft: '1px solid var(--border-hairline)',
      font: 'var(--type-data-sm)',
      whiteSpace: 'nowrap'
    }
  }, [['TICK', '+412', 'var(--green-500)'], ['ADD', '+820', 'var(--green-500)'], ['VOLD', '+1.4B', 'var(--green-500)'], ['0DTE', '61%', 'var(--amber-500)']].map(([l, v, c]) => /*#__PURE__*/React.createElement("span", {
    key: l,
    style: {
      display: 'inline-flex',
      gap: 5,
      alignItems: 'baseline'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-muted)',
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)'
    }
  }, l), /*#__PURE__*/React.createElement("span", {
    style: {
      color: c,
      fontVariantNumeric: 'tabular-nums'
    }
  }, v)))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "long",
    dot: true,
    pulse: true
  }, "Market open"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-sm)',
      color: 'var(--text-muted)'
    }
  }, "14:32:07 ET"), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 28,
      height: 28,
      borderRadius: '50%',
      background: 'var(--surface-raised)',
      border: '1px solid var(--border-default)',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      font: '600 11px var(--font-mono)',
      color: 'var(--green-400)'
    }
  }, "JD")));
}
const NAV_ITEMS = [{
  id: 'signals',
  label: 'Signals',
  icon: 'zap'
}, {
  id: 'chart',
  label: 'Chart',
  icon: 'chart-candlestick'
}, {
  id: 'scanner',
  label: 'Scanner',
  icon: 'radar'
}, {
  id: 'gex',
  label: 'GEX',
  icon: 'flame'
}, {
  id: 'portfolio',
  label: 'P&L',
  icon: 'wallet'
}, {
  id: 'settings',
  label: 'Alerts & Settings',
  icon: 'settings'
}];
function NavIcon({
  name
}) {
  return /*#__PURE__*/React.createElement(Icon, {
    name: name,
    size: 16
  });
}
function SideRail({
  view,
  onNav
}) {
  return /*#__PURE__*/React.createElement("nav", {
    style: {
      width: 'var(--sidebar-width)',
      flexShrink: 0,
      background: 'var(--bg-0)',
      borderRight: '1px solid var(--border-hairline)',
      padding: '12px 8px',
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, NAV_ITEMS.map(item => {
    const active = view === item.id || item.id === 'signals' && view === 'detail';
    return /*#__PURE__*/React.createElement("button", {
      key: item.id,
      onClick: () => onNav(item.id),
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '9px 12px',
        background: active ? 'var(--green-dim)' : 'transparent',
        color: active ? 'var(--green-400)' : 'var(--text-secondary)',
        border: 'none',
        borderRadius: 'var(--radius-sm)',
        cursor: 'pointer',
        font: '600 13px/1 var(--font-sans)',
        textAlign: 'left',
        width: '100%',
        transition: 'background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out)'
      }
    }, /*#__PURE__*/React.createElement(NavIcon, {
      name: item.icon,
      active: active
    }), item.label);
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 'auto',
      padding: '10px 12px',
      borderTop: '1px solid var(--border-hairline)',
      display: 'flex',
      flexDirection: 'column',
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-label)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)'
    }
  }, "Session P&L"), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-data-lg)',
      color: 'var(--green-500)'
    }
  }, "+$1,284.50")));
}

// SVG candlestick chart
function CandleChart({
  candles,
  height = 320,
  levels = []
}) {
  const w = 1000,
    h = height;
  const padR = 56,
    padB = 26;
  const all = candles.flatMap(c => [c.high, c.low]).concat(levels.map(l => l.price));
  const min = Math.min(...all),
    max = Math.max(...all);
  const range = max - min || 1;
  const y = p => 8 + (1 - (p - min) / range) * (h - padB - 16);
  const cw = (w - padR) / candles.length;
  const gridLines = 5;
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${w} ${h}`,
    style: {
      width: '100%',
      height: '100%',
      display: 'block',
      background: 'var(--surface-inset)',
      borderRadius: 'var(--radius-sm)'
    },
    preserveAspectRatio: "none"
  }, Array.from({
    length: gridLines
  }, (_, i) => {
    const p = min + range * i / (gridLines - 1);
    return /*#__PURE__*/React.createElement("g", {
      key: i
    }, /*#__PURE__*/React.createElement("line", {
      x1: "0",
      x2: w - padR,
      y1: y(p),
      y2: y(p),
      stroke: "rgba(151,176,164,0.07)",
      strokeWidth: "1"
    }), /*#__PURE__*/React.createElement("text", {
      x: w - padR + 8,
      y: y(p) + 3,
      fill: "var(--text-muted)",
      style: {
        font: '500 10px var(--font-mono)'
      }
    }, p.toFixed(2)));
  }), candles.map((c, i) => {
    const up = c.close >= c.open;
    const color = up ? 'var(--green-500)' : 'var(--red-500)';
    const x = i * cw + cw / 2;
    const bw = Math.max(2, cw * 0.55);
    return /*#__PURE__*/React.createElement("g", {
      key: i
    }, /*#__PURE__*/React.createElement("line", {
      x1: x,
      x2: x,
      y1: y(c.high),
      y2: y(c.low),
      stroke: color,
      strokeWidth: "1",
      opacity: "0.8"
    }), /*#__PURE__*/React.createElement("rect", {
      x: x - bw / 2,
      y: y(Math.max(c.open, c.close)),
      width: bw,
      height: Math.max(1, Math.abs(y(c.open) - y(c.close))),
      fill: color,
      opacity: up ? 0.9 : 0.85
    }), /*#__PURE__*/React.createElement("rect", {
      x: x - bw / 2,
      y: h - padB + 6,
      width: bw,
      height: c.vol * (padB - 10),
      fill: color,
      opacity: "0.25"
    }));
  }), levels.map((l, i) => /*#__PURE__*/React.createElement("g", {
    key: `l${i}`
  }, /*#__PURE__*/React.createElement("line", {
    x1: "0",
    x2: w - padR,
    y1: y(l.price),
    y2: y(l.price),
    stroke: l.color,
    strokeWidth: "1",
    strokeDasharray: "6 4",
    opacity: "0.8"
  }), /*#__PURE__*/React.createElement("rect", {
    x: w - padR + 2,
    y: y(l.price) - 8,
    width: padR - 4,
    height: "16",
    rx: "3",
    fill: l.color
  }), /*#__PURE__*/React.createElement("text", {
    x: w - padR + padR / 2,
    y: y(l.price) + 3.5,
    textAnchor: "middle",
    fill: "#04120A",
    style: {
      font: '700 9.5px var(--font-mono)'
    }
  }, l.label))));
}
function PanelTitle({
  children,
  right
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 8,
      marginBottom: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-title)',
      color: 'var(--text-primary)'
    }
  }, children), right);
}
Object.assign(window, {
  Icon,
  TopBar,
  SideRail,
  CandleChart,
  PanelTitle,
  Wordmark
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/chrome.jsx", error: String((e && e.message) || e) }); }

// ui_kits/terminal/data.js
try { (() => {
// SuperTrades terminal — shared fake data + chart helpers
(function () {
  // Deterministic PRNG so charts look identical across loads
  function mulberry32(a) {
    return function () {
      a |= 0;
      a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function genCandles(seed, n, start) {
    const rnd = mulberry32(seed);
    const candles = [];
    let price = start;
    for (let i = 0; i < n; i++) {
      const drift = (rnd() - 0.47) * (start * 0.004);
      const open = price;
      const close = price + drift;
      const high = Math.max(open, close) + rnd() * (start * 0.0018);
      const low = Math.min(open, close) - rnd() * (start * 0.0018);
      const vol = 0.4 + rnd() * 0.6;
      candles.push({
        open,
        close,
        high,
        low,
        vol
      });
      price = close;
    }
    return candles;
  }
  const WATCHLIST = [{
    sym: 'NVDA',
    last: 412.5,
    chg: 2.41,
    vol: '48.2M',
    atr: 4.12,
    conf: 82,
    spread: 0.02
  }, {
    sym: 'SPY',
    last: 598.42,
    chg: 0.42,
    vol: '61.4M',
    atr: 2.85,
    conf: 74,
    spread: 0.01
  }, {
    sym: 'TSLA',
    last: 244.18,
    chg: -0.87,
    vol: '92.1M',
    atr: 6.4,
    conf: 51,
    spread: 0.03
  }, {
    sym: 'AMD',
    last: 162.33,
    chg: 1.12,
    vol: '38.7M',
    atr: 3.05,
    conf: 38,
    spread: 0.02
  }, {
    sym: 'QQQ',
    last: 512.09,
    chg: 0.87,
    vol: '44.9M',
    atr: 3.4,
    conf: 66,
    spread: 0.01
  }, {
    sym: 'META',
    last: 688.71,
    chg: -0.34,
    vol: '12.3M',
    atr: 8.2,
    conf: 45,
    spread: 0.05
  }, {
    sym: 'COIN',
    last: 301.55,
    chg: 3.28,
    vol: '18.8M',
    atr: 11.6,
    conf: 71,
    spread: 0.08
  }, {
    sym: 'MSTR',
    last: 422.9,
    chg: -2.11,
    vol: '9.4M',
    atr: 15.2,
    conf: 29,
    spread: 0.12
  }];
  const SIGNALS = [{
    id: 'SG-8842',
    direction: 'long',
    symbol: 'NVDA',
    strategy: 'Squeeze confluence · 5m',
    entry: '412.50',
    stop: '411.80',
    target: '414.10',
    rr: '1 : 2.3',
    confidence: 82,
    time: '14:32:07',
    live: true,
    thesis: 'Price reclaimed VWAP on rising volume after holding the 411.80 shelf through two tests. Spot pressing the 415 king node from below in a −gamma pocket — dealers chase; 415C 0DTE swept at ask ($2.4M).',
    status: null,
    factors: [{
      label: 'King node 415',
      kind: 'gex',
      fired: true,
      detail: '+1.85B pin above — magnet'
    }, {
      label: 'Squeeze regime',
      kind: 'gex',
      fired: true,
      detail: '−gamma pocket 409–410, dealers chase moves'
    }, {
      label: 'Unusual flow',
      kind: 'flow',
      fired: true,
      detail: '5,100× 415C 0DTE at ask · $2.4M'
    }, {
      label: 'VWAP reclaim',
      kind: 'ta',
      fired: true,
      detail: 'Held 411.80 shelf ×2, reclaimed on volume'
    }, {
      label: 'HVN shelf 411.80',
      kind: 'hvn',
      fired: true,
      detail: 'Stop tucked under high-volume node'
    }, {
      label: 'RVOL 1.8×',
      kind: 'ta',
      fired: true,
      detail: 'Above 1.5× threshold'
    }, {
      label: 'Catalyst clear',
      kind: 'news',
      fired: true,
      detail: 'No earnings 5d · Fed speaker 15:00 — exit before'
    }, {
      label: 'Above gamma flip',
      kind: 'gex',
      fired: true,
      detail: 'Spot 413.11 > flip 409.50'
    }, {
      label: 'Index aligned',
      kind: 'mkt',
      fired: true,
      detail: 'QQQ +0.87% · TICK +412 — tailwind'
    }, {
      label: '14:30–15:00 window',
      kind: 'time',
      fired: true,
      detail: 'A-tier: 0DTE charm flows active'
    }]
  }, {
    id: 'SG-8841',
    direction: 'short',
    symbol: 'TSLA',
    strategy: 'Gamma flip break · 1m',
    entry: '244.60',
    stop: '245.20',
    target: '243.10',
    rr: '1 : 2.5',
    confidence: 71,
    time: '14:27:44',
    live: true,
    thesis: 'Breakout above 245 failed on declining volume as spot lost the 243.80 gamma flip — negative gamma regime opens the range. 240P 0DTE sweeps confirm. Targeting the morning gap fill at 243.10.',
    status: null,
    factors: [{
      label: 'Gamma flip break',
      kind: 'gex',
      fired: true,
      detail: 'Lost 243.80 → −gamma regime'
    }, {
      label: 'Unusual flow',
      kind: 'flow',
      fired: true,
      detail: '6,400× 240P 0DTE at ask · $860K'
    }, {
      label: 'Failed breakout',
      kind: 'ta',
      fired: true,
      detail: '245 push absorbed, lower high'
    }, {
      label: 'LVN below',
      kind: 'hvn',
      fired: true,
      detail: 'Thin volume 243.8→243.1 — fast travel'
    }, {
      label: 'Negative news',
      kind: 'news',
      fired: true,
      detail: 'Deliveries miss headline 14:20'
    }, {
      label: 'King node',
      kind: 'gex',
      fired: false,
      detail: 'No node below until 240 — open air'
    }, {
      label: 'RVOL 2.1×',
      kind: 'ta',
      fired: true,
      detail: 'Expansion volume on the break'
    }, {
      label: 'Index aligned',
      kind: 'mkt',
      fired: true,
      detail: 'Relative weakness vs flat SPY'
    }]
  }, {
    id: 'SG-8840',
    direction: 'long',
    symbol: 'COIN',
    strategy: 'ORB + flow · 5m',
    entry: '299.80',
    stop: '298.40',
    target: '303.20',
    rr: '1 : 2.4',
    confidence: 74,
    time: '14:12:19',
    live: false,
    status: 'Target',
    thesis: 'Opening range breakout continuation with sector momentum and unusual call buying at the lows.',
    factors: [{
      label: 'Unusual flow',
      kind: 'flow',
      fired: true,
      detail: '4,200× 300C 0DTE at ask · $1.9M'
    }, {
      label: 'ORB continuation',
      kind: 'ta',
      fired: true,
      detail: 'Held ORH retest'
    }, {
      label: 'Above gamma flip',
      kind: 'gex',
      fired: true,
      detail: 'Spot > flip 296.50'
    }]
  }, {
    id: 'SG-8839',
    direction: 'long',
    symbol: 'AMD',
    strategy: 'Trend pullback · 15m',
    entry: '161.90',
    stop: '161.20',
    target: '163.50',
    rr: '1 : 2.3',
    confidence: 58,
    time: '13:48:02',
    live: false,
    status: 'Stopped',
    thesis: 'Pullback to rising 20EMA in an uptrend; invalidated on the 161.20 break. TA-only setup — no GEX or flow confirmation.',
    factors: [{
      label: '20EMA pullback',
      kind: 'ta',
      fired: true,
      detail: 'Rising 15m trend'
    }, {
      label: 'GEX support',
      kind: 'gex',
      fired: false,
      detail: 'No node at entry — unprotected'
    }, {
      label: 'Flow confirm',
      kind: 'flow',
      fired: false,
      detail: 'No sweeps — low conviction'
    }, {
      label: 'Index fighting',
      kind: 'mkt',
      fired: false,
      veto: true,
      detail: 'VETO: TICK −4 min streak — should have blocked entry'
    }, {
      label: '13:30–14:00 chop',
      kind: 'time',
      fired: false,
      detail: 'C-tier window — lunch drift'
    }]
  }, {
    id: 'SG-8838',
    direction: 'short',
    symbol: 'META',
    strategy: 'Range fade at call wall · 5m',
    entry: '689.90',
    stop: '691.10',
    target: '686.80',
    rr: '1 : 2.6',
    confidence: 63,
    time: '13:22:37',
    live: false,
    status: 'Filled',
    thesis: 'Fading the top of a three-hour range into the 690 call wall on weakening breadth.',
    factors: [{
      label: 'Call wall 690',
      kind: 'gex',
      fired: true,
      detail: '+gamma cap — dealers sell into it'
    }, {
      label: 'Range top',
      kind: 'ta',
      fired: true,
      detail: 'Third rejection, breadth fading'
    }, {
      label: 'Flow confirm',
      kind: 'flow',
      fired: false,
      detail: 'No put sweeps yet'
    }]
  }];
  const POSITIONS = [{
    sym: 'NVDA',
    side: 'long',
    qty: 200,
    avg: '412.52',
    last: '413.11',
    pnl: 118.0,
    pnlPct: '+0.14%',
    r: '+0.8R'
  }, {
    sym: 'TSLA',
    side: 'short',
    qty: 150,
    avg: '244.58',
    last: '244.21',
    pnl: 55.5,
    pnlPct: '+0.15%',
    r: '+0.6R'
  }];
  const TRADES = [{
    time: '14:12',
    sym: 'COIN',
    side: 'long',
    in: '299.80',
    out: '303.20',
    r: '+2.4R',
    pnl: '+$680.00'
  }, {
    time: '13:48',
    sym: 'AMD',
    side: 'long',
    in: '161.90',
    out: '161.20',
    r: '−1.0R',
    pnl: '−$210.00'
  }, {
    time: '13:22',
    sym: 'META',
    side: 'short',
    in: '689.90',
    out: '687.55',
    r: '+1.9R',
    pnl: '+$470.00'
  }, {
    time: '11:56',
    sym: 'SPY',
    side: 'long',
    in: '596.80',
    out: '598.10',
    r: '+1.6R',
    pnl: '+$390.00'
  }, {
    time: '10:41',
    sym: 'NVDA',
    side: 'short',
    in: '409.90',
    out: '410.60',
    r: '−1.0R',
    pnl: '−$175.00'
  }, {
    time: '09:52',
    sym: 'QQQ',
    side: 'long',
    in: '509.40',
    out: '511.30',
    r: '+2.1R',
    pnl: '+$532.00'
  }];

  // GEX by strike (NVDA) — positive = dealers long gamma (pinning), negative = short gamma (fuel)
  const GEX = {
    symbol: 'NVDA',
    spot: 413.11,
    flip: 409.5,
    kingNode: 415,
    callWall: 420,
    putWall: 405,
    hvl: 412.5,
    strikes: [{
      k: 395,
      gex: -0.42
    }, {
      k: 400,
      gex: -0.88
    }, {
      k: 402.5,
      gex: -0.61
    }, {
      k: 405,
      gex: -1.35
    }, {
      k: 407.5,
      gex: -0.52
    }, {
      k: 409,
      gex: -0.18
    }, {
      k: 410,
      gex: 0.24
    }, {
      k: 412.5,
      gex: 0.96
    }, {
      k: 415,
      gex: 1.85
    }, {
      k: 417.5,
      gex: 0.74
    }, {
      k: 420,
      gex: 1.42
    }, {
      k: 422.5,
      gex: 0.38
    }, {
      k: 425,
      gex: 0.2
    }]
  };
  const GEX_ALERTS = [{
    time: '14:31:52',
    sym: 'NVDA',
    kind: 'squeeze',
    text: 'Short-gamma squeeze setup — spot pressing 415 king node from below, dealers chasing'
  }, {
    time: '14:29:10',
    sym: 'TSLA',
    kind: 'flip',
    text: 'Crossed gamma flip 243.80 → negative gamma regime, expect expanded range'
  }, {
    time: '14:24:36',
    sym: 'SPY',
    kind: 'highvol',
    text: 'HIGH VOL: RVOL 3.2× at 598 node · IV 5m +14%'
  }, {
    time: '14:18:04',
    sym: 'COIN',
    kind: 'unusual',
    text: 'Unusual buying at lows — 4,200× 300C 0DTE swept at ask ($1.9M)'
  }];
  const FLOW = [{
    time: '14:31:44',
    sym: 'NVDA',
    strike: '415C',
    exp: '0DTE',
    side: 'BUY',
    prem: '$2.4M',
    size: '5,100×',
    at: 'ask',
    otm: '0.5%'
  }, {
    time: '14:28:12',
    sym: 'NVDA',
    strike: '420C',
    exp: '2d',
    side: 'BUY',
    prem: '$1.1M',
    size: '3,800×',
    at: 'ask',
    otm: '1.7%'
  }, {
    time: '14:22:51',
    sym: 'TSLA',
    strike: '240P',
    exp: '0DTE',
    side: 'BUY',
    prem: '$860K',
    size: '6,400×',
    at: 'ask',
    otm: '1.8%'
  }, {
    time: '14:18:04',
    sym: 'COIN',
    strike: '300C',
    exp: '0DTE',
    side: 'BUY',
    prem: '$1.9M',
    size: '4,200×',
    at: 'ask',
    otm: '0.6%'
  }, {
    time: '14:11:37',
    sym: 'SPY',
    strike: '600C',
    exp: '1d',
    side: 'SELL',
    prem: '$720K',
    size: '9,000×',
    at: 'bid',
    otm: '0.3%'
  }];

  // Sector universe — 2-3 deepest options books per sector, not just indexes
  const SECTORS = [{
    name: 'Indexes',
    etf: 'SPY',
    regime: '+gamma · pinned',
    chg: 0.42,
    names: [{
      sym: 'SPY',
      last: 598.42,
      chg: 0.42,
      optVol: '8.4M',
      spread: 0.01,
      ivr: 12,
      conv: 61,
      setup: 'Range pin at 600 call wall'
    }, {
      sym: 'QQQ',
      last: 512.09,
      chg: 0.87,
      optVol: '3.9M',
      spread: 0.01,
      ivr: 18,
      conv: 66,
      setup: 'VWAP hold, king node above'
    }]
  }, {
    name: 'Semis',
    etf: 'SMH',
    regime: '−gamma · expansion',
    chg: 1.94,
    names: [{
      sym: 'NVDA',
      last: 412.5,
      chg: 2.41,
      optVol: '2.8M',
      spread: 0.02,
      ivr: 34,
      conv: 82,
      setup: 'Squeeze into 415 king node'
    }, {
      sym: 'AMD',
      last: 162.33,
      chg: 1.12,
      optVol: '840K',
      spread: 0.02,
      ivr: 28,
      conv: 48,
      setup: 'Trend pullback, no flow confirm'
    }, {
      sym: 'AVGO',
      last: 1710.4,
      chg: 1.63,
      optVol: '310K',
      spread: 0.35,
      ivr: 41,
      conv: 55,
      setup: 'ORB hold, wide spreads — size down'
    }]
  }, {
    name: 'Mega-cap',
    etf: 'XLK',
    regime: '+gamma · pinned',
    chg: 0.61,
    names: [{
      sym: 'TSLA',
      last: 244.18,
      chg: -0.87,
      optVol: '2.1M',
      spread: 0.03,
      ivr: 47,
      conv: 71,
      setup: 'Gamma flip break, gap fill below'
    }, {
      sym: 'META',
      last: 688.71,
      chg: -0.34,
      optVol: '620K',
      spread: 0.05,
      ivr: 22,
      conv: 63,
      setup: 'Fade at 690 call wall'
    }, {
      sym: 'AAPL',
      last: 232.66,
      chg: 0.18,
      optVol: '1.4M',
      spread: 0.01,
      ivr: 9,
      conv: 31,
      setup: 'Chop — IV too low, skip'
    }]
  }, {
    name: 'Crypto-linked',
    etf: 'BITO',
    regime: '−gamma · fuel',
    chg: 2.86,
    names: [{
      sym: 'COIN',
      last: 301.55,
      chg: 3.28,
      optVol: '480K',
      spread: 0.08,
      ivr: 58,
      conv: 74,
      setup: 'ORB continuation + call sweeps'
    }, {
      sym: 'MSTR',
      last: 422.9,
      chg: -2.11,
      optVol: '390K',
      spread: 0.12,
      ivr: 66,
      conv: 42,
      setup: 'High IV crush risk — wait'
    }]
  }];

  // Ranked best setups across the universe (conviction = fired factors × weights)
  const BEST_SETUPS = [{
    rank: 1,
    sym: 'NVDA',
    direction: 'long',
    conv: 82,
    fired: '6/6',
    setup: 'Squeeze into 415 king node',
    sector: 'Semis',
    note: '−gamma pocket + $2.4M 0DTE sweeps + VWAP reclaim'
  }, {
    rank: 2,
    sym: 'COIN',
    direction: 'long',
    conv: 74,
    fired: '3/3',
    setup: 'ORB continuation + flow',
    sector: 'Crypto-linked',
    note: 'Sector leading, calls swept at lows'
  }, {
    rank: 3,
    sym: 'TSLA',
    direction: 'short',
    conv: 71,
    fired: '4/5',
    setup: 'Gamma flip break',
    sector: 'Mega-cap',
    note: '−gamma regime opened, open air to 240'
  }];
  const CATALYSTS = [{
    time: '15:00',
    kind: 'macro',
    label: 'Fed speaker (Waller)',
    impact: 'high',
    note: 'Rate-path comments — flatten scalps 5m before'
  }, {
    time: '14:20',
    kind: 'news',
    label: 'TSLA deliveries miss',
    impact: 'high',
    note: 'Headline driving the flip break — confirms short'
  }, {
    time: '13:45',
    kind: 'sector',
    label: 'Semis bid on TSM guidance',
    impact: 'med',
    note: 'SMH leading — tailwind for NVDA long'
  }, {
    time: '10:00',
    kind: 'macro',
    label: 'ISM Services beat',
    impact: 'med',
    note: 'Priced in — no follow-through'
  }, {
    time: 'AMC',
    kind: 'earnings',
    label: 'No earnings in universe today',
    impact: 'low',
    note: 'COIN reports Thu — IV already building'
  }];
  window.ST_DATA = {
    genCandles,
    WATCHLIST,
    SIGNALS,
    POSITIONS,
    TRADES,
    GEX,
    GEX_ALERTS,
    FLOW,
    SECTORS,
    BEST_SETUPS,
    CATALYSTS
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/terminal/data.js", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Tabs = __ds_scope.Tabs;

__ds_ns.Toast = __ds_scope.Toast;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.ConfidenceMeter = __ds_scope.ConfidenceMeter;

__ds_ns.DataTable = __ds_scope.DataTable;

__ds_ns.SignalCard = __ds_scope.SignalCard;

__ds_ns.StatCard = __ds_scope.StatCard;

__ds_ns.TickerChip = __ds_scope.TickerChip;

})();
