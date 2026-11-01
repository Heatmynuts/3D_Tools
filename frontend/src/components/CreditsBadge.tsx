import { useEffect, useRef, useState } from 'react'
import type { Credits } from '../types'

const usd = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(2)} $`)

/** Top-bar credit summary. Only provider-reported numbers are shown as real balances. */
export function CreditsBadge({ credits }: { credits: Credits | null }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  if (!credits) return null

  const or = credits.openrouter
  const orShown = or?.account_balance_usd ?? or?.key_limit_remaining_usd
  const an = credits.anthropic
  const parts: string[] = []
  if (or) parts.push(`OpenRouter ${orShown != null ? usd(orShown) : 'n/d'}`)
  if (an) parts.push(`Claude ${an.estimated_balance_usd != null ? '≈ ' + usd(an.estimated_balance_usd) : 'n/d'}`)

  return (
    <div className="credits" ref={box}>
      <button className="credits-btn" onClick={() => setOpen((o) => !o)} title="Crédits et consommation">
        {parts.length ? parts.join(' · ') : 'Crédits'}
      </button>
      {open && (
        <div className="credits-pop">
          <h4>OpenRouter</h4>
          {!or && <p className="muted small">Pas de clé OpenRouter configurée.</p>}
          {or && (
            <ul className="kv">
              {or.account_balance_usd != null && <li><span className="k">Solde du compte</span><span className="v">{usd(or.account_balance_usd)}</span></li>}
              {or.key_limit_remaining_usd != null && <li><span className="k">Reste sur la limite de la clé</span><span className="v">{usd(or.key_limit_remaining_usd)}</span></li>}
              <li><span className="k">Consommé (clé, total)</span><span className="v">{usd(or.key_usage_usd)}</span></li>
              <li><span className="k">Aujourd’hui / ce mois</span><span className="v">{usd(or.usage_daily_usd)} / {usd(or.usage_monthly_usd)}</span></li>
            </ul>
          )}
          {or && or.account_balance_usd == null && (
            <p className="muted small">Le solde du compte nécessite une clé de gestion : OPENROUTER_MANAGEMENT_KEY dans backend/.env.</p>
          )}
          {or?.error && <p className="picker-err">{or.error}</p>}

          <h4>Anthropic (Claude)</h4>
          {!an && <p className="muted small">Pas de clé Anthropic configurée.</p>}
          {an && (
            <>
              {an.estimated_balance_usd != null ? (
                <ul className="kv">
                  <li><span className="k">Solde estimé</span><span className="v">≈ {usd(an.estimated_balance_usd)}</span></li>
                  <li><span className="k">Dépensé depuis la référence</span><span className="v">{usd(an.spent_since_usd)}</span></li>
                </ul>
              ) : null}
              <p className="muted small">
                {an.note} {an.estimated_balance_usd != null
                  ? `Estimation : ${an.reference}, moins les coûts calculés dans cette appli.`
                  : 'Pour une estimation, renseigne ANTHROPIC_CREDIT_BALANCE et ANTHROPIC_CREDIT_DATE dans backend/.env.'}
              </p>
            </>
          )}

          <h4>Dépensé via cette appli</h4>
          <ul className="kv">
            <li><span className="k">Claude (aujourd’hui / total)</span><span className="v">{usd(credits.app.anthropic?.today_usd)} / {usd(credits.app.anthropic?.total_usd)}</span></li>
            <li><span className="k">OpenRouter (aujourd’hui / total)</span><span className="v">{usd(credits.app.openai_compat?.today_usd)} / {usd(credits.app.openai_compat?.total_usd)}</span></li>
          </ul>
        </div>
      )}
    </div>
  )
}
