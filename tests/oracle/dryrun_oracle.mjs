// Parity oracle: Normalizer/Synthesizer/Reporter-interp logic transcribed verbatim from
// smse-pipeline-dryrun.jsx (Drive 1Shn7KKXBKp744spwcGjR5eJ169xLFrSZ, T0-authorized 2026-04-30).
// UI stripped. Used only to generate tests/golden/*.json. Usage: node dryrun_oracle.mjs <raw.json>
import { readFileSync } from "node:fs";
const RAW_INPUTS = JSON.parse(readFileSync(process.argv[2], "utf8"));
function NormalizerAgent(asset, raw) {
  const { cot_raw, options_raw, etf_flows_raw, price_raw } = raw;
  const net = cot_raw.noncommercial_long - cot_raw.noncommercial_short;
  const hist = cot_raw.historical_net;
  const mean = hist.reduce((a, b) => a + b, 0) / hist.length;
  const std = Math.sqrt(hist.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / hist.length);
  const z_score = parseFloat(((net - mean) / std).toFixed(2));
  const stale = cot_raw.data_age_days > 7;
  let cot_bias, extreme_flag, risk_note;
  if (stale) { cot_bias = "Neutral"; extreme_flag = "None"; risk_note = "Normal"; } else {
    cot_bias = z_score > 1.5 ? "StrongLong" : z_score > 0.5 ? "Long" : z_score < -1.5 ? "StrongShort" : z_score < -0.5 ? "Short" : "Neutral";
    extreme_flag = z_score > 1.5 ? "BullishExtreme" : z_score < -1.5 ? "BearishExtreme" : "None";
    risk_note = Math.abs(z_score) > 1.5 ? (z_score > 0 ? "CrowdedLong" : "CrowdedShort") : "Normal";
  }
  let call_gex = 0, put_gex = 0;
  const byGex = options_raw.chain.map(s => { const cg = s.call_gamma * s.call_oi; const pg = s.put_gamma * s.put_oi; call_gex += cg; put_gex += pg; return { strike: s.strike, net_gex: cg - pg }; });
  const net_gamma = parseFloat((call_gex - put_gex).toFixed(4));
  const total_gamma = parseFloat((call_gex + put_gex).toFixed(4));
  let gamma_flip_level = null;
  for (let i = 0; i < byGex.length - 1; i++) {
    if (byGex[i].net_gex <= 0 && byGex[i+1].net_gex > 0 || byGex[i].net_gex >= 0 && byGex[i+1].net_gex < 0) {
      const a = byGex[i], b = byGex[i+1];
      gamma_flip_level = Math.round(a.strike + (b.strike - a.strike) * (Math.abs(a.net_gex) / (Math.abs(a.net_gex) + Math.abs(b.net_gex))));
      break;
    }
  }
  if (!gamma_flip_level) gamma_flip_level = Math.round(options_raw.underlying_price * 0.99);
  const gamma_regime = net_gamma > 0 ? "LongGamma" : net_gamma < 0 ? "ShortGamma" : "Neutral";
  const sorted_magnets = [...byGex].sort((a, b) => Math.abs(b.net_gex) - Math.abs(a.net_gex)).slice(0, 3).map(s => s.strike);
  const volatility_note = gamma_regime === "LongGamma" ? "VolSuppressing" : gamma_regime === "ShortGamma" ? "VolAmplifying" : "Neutral";
  const flow_threshold = 0.001 * etf_flows_raw.shares_outstanding;
  const net_flow = etf_flows_raw.inflow - etf_flows_raw.outflow;
  const flow_bias = net_flow > flow_threshold ? "FlowLong" : net_flow < -flow_threshold ? "FlowShort" : "Mixed";
  const crowding = (flow_bias === "FlowLong" && (cot_bias === "StrongLong" || cot_bias === "Long")) || (flow_bias === "FlowShort" && (cot_bias === "StrongShort" || cot_bias === "Short")) ? "Crowded" : "NotCrowded";
  const { close, moving_averages: ma } = price_raw;
  const trend = close > ma.ma50 && ma.ma50 > ma.ma200 ? "Up" : close < ma.ma50 && ma.ma50 < ma.ma200 ? "Down" : "Neutral";
  return { cot: { net, z_score, bias: cot_bias, extreme_flag, risk_note, stale },
    gamma: { total_gamma, net_gamma, regime: gamma_regime, gamma_flip_level, gamma_magnets: sorted_magnets.sort((a,b)=>a-b), volatility_note },
    flows: { net_flow, flow_threshold, flow_bias, crowding }, price: { trend, close, ma20: ma.ma20, ma50: ma.ma50, ma200: ma.ma200 } };
}
function SMSESynthesizerAgent(asset, timestamp, norm) {
  const { cot, gamma, flows, price } = norm;
  let primary;
  if (price.trend === "Up" && gamma.regime === "LongGamma") primary = "StableUp";
  else if (price.trend === "Down" && gamma.regime === "ShortGamma") primary = "StableDown";
  else if (price.trend === "Up" && gamma.regime === "ShortGamma") primary = "VolatileUp";
  else if (price.trend === "Down" && gamma.regime === "LongGamma") primary = "VolatileDown";
  else primary = "Transition";
  const risk_note = cot.risk_note === "CrowdedLong" ? "CrowdedLong" : cot.risk_note === "CrowdedShort" ? "CrowdedShort" : "Uncrowded";
  const support = [Math.round(price.ma50), Math.round(price.ma200)].sort((a, b) => b - a).filter(v => v < price.close);
  const resistance = [Math.round(price.close * 1.01), Math.round(price.close * 1.025)];
  return { asset, timestamp, cot: { bias: cot.bias, z_score: cot.z_score, extreme_flag: cot.extreme_flag, risk_note: cot.risk_note, stale: cot.stale },
    gamma: { regime: gamma.regime, gamma_flip_level: gamma.gamma_flip_level, volatility_note: gamma.volatility_note, gamma_magnets: gamma.gamma_magnets },
    flows: { bias: flows.flow_bias, crowding: flows.crowding, flow_threshold: flows.flow_threshold },
    regime: { primary, risk_note }, key_levels: { support, resistance, gamma_magnets: gamma.gamma_magnets } };
}
const interp = (a) => { let t = "";
  switch (a.regime.primary) {
    case "StableUp": t += "Trend intact. Dips likely supported unless price breaks below gamma flip."; break;
    case "StableDown": t += "Downtrend intact. Rallies likely sold unless flows turn positive."; break;
    case "VolatileUp": t += "Upside path but unstable. Expect sharp swings around gamma flip."; break;
    case "VolatileDown": t += "Downside path with amplified volatility. Squeeze risk if flows flip."; break;
    case "Transition": t += "Regime shift forming. Watch gamma flip and flow direction for confirmation."; break; }
  if (a.regime.risk_note === "CrowdedLong") t += " Crowded long — air-pocket risk if flows reverse.";
  if (a.regime.risk_note === "CrowdedShort") t += " Crowded short — high squeeze potential.";
  if (a.cot.stale) t += " ⚠ COT stale (>7d) — directional bias unreliable.";
  return t; };
const timestamp = "2026-04-30T21:00:00Z";
const out = {};
for (const asset of Object.keys(RAW_INPUTS)) {
  const norm = NormalizerAgent(asset, RAW_INPUTS[asset]);
  const smse = SMSESynthesizerAgent(asset, timestamp, norm);
  out[asset] = { norm, smse, interpretation: interp(smse) };
}
process.stdout.write(JSON.stringify(out, null, 2) + "\n");
