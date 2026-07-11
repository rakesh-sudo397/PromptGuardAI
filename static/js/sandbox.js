async function executeSecurityCheck() {
    const promptText = document.getElementById('txtPrompt').value.trim();
    if (!promptText) return alert("Prompt string cannot be empty.");

    const scanBtn = document.querySelector('.btn-primary');
    const originalBtnText = scanBtn.innerText;
    scanBtn.innerText = 'Evaluating Security...';
    scanBtn.disabled = true;

    // Retrieve active toggles
    const enableScrub = document.getElementById('chkScrub')?.checked || false;
    const enableRedact = document.getElementById('chkRedact')?.checked || false;
    const enableFirewall = document.getElementById('chkFirewall')?.checked || false;
    const enableShadow = document.getElementById('chkShadow')?.checked || false;
    const enableStream = document.getElementById('chkStream')?.checked || false;
    
    // Retrieve downstream target settings
    const downstreamType = document.getElementById('selDownstreamType')?.value || 'mock';
    const downstreamModel = document.getElementById('txtDownstreamModel')?.value.trim() || '';
    const downstreamToken = document.getElementById('txtDownstreamToken')?.value.trim() || '';

    // Reset UI cards
    const outputContainer = document.getElementById('pnlOutput');
    outputContainer.style.display = 'none';
    
    const piiCard = document.getElementById('cardPii');
    const scrubCard = document.getElementById('cardScrub');
    const firewallCard = document.getElementById('cardFirewall');
    const shadowCard = document.getElementById('cardShadow');
    
    if (piiCard) piiCard.style.display = 'none';
    if (scrubCard) scrubCard.style.display = 'none';
    if (firewallCard) firewallCard.style.display = 'none';
    if (shadowCard) shadowCard.style.display = 'none';

    // 1. Streaming response loop
    if (enableStream) {
        firewallCard.style.display = 'block';
        document.getElementById('lblFirewallStatus').innerText = 'Streaming...';
        document.getElementById('lblFirewallStatus').className = 'badge bg-green';
        const valFirewallText = document.getElementById('valFirewallText');
        valFirewallText.innerText = '';
        
        try {
            const res = await fetch("/api/v1/scan/stream", {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    prompt: promptText,
                    enable_scrub: enableScrub,
                    enable_redact: enableRedact,
                    enable_firewall: enableFirewall,
                    downstream_type: downstreamType,
                    downstream_model: downstreamModel,
                    downstream_token: downstreamToken
                })
            });
            
            if (res.status === 401) {
                alert("Security error: 401 Unauthorized API Key.");
                scanBtn.innerText = originalBtnText;
                scanBtn.disabled = false;
                return;
            }
            
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let done = false;
            
            outputContainer.style.display = 'block';
            const decisionBadge = document.getElementById('lblDecision');
            decisionBadge.innerText = 'Evaluating...';
            decisionBadge.className = 'badge bg-green';
            
            while (!done) {
                const { value, done: readerDone } = await reader.read();
                done = readerDone;
                if (value) {
                    const chunk = decoder.decode(value, { stream: !done });
                    const lines = chunk.split("\n");
                    for (const line of lines) {
                        if (line.startsWith("data: ")) {
                            try {
                                const data = JSON.parse(line.substring(6));
                                if (data.event === "block") {
                                    decisionBadge.innerText = 'BLOCKED / THREAT';
                                    decisionBadge.className = 'badge bg-red';
                                    outputContainer.style.borderColor = 'rgba(244, 63, 94, 0.4)';
                                    
                                    document.getElementById('lblFirewallStatus').innerText = 'Blocked';
                                    document.getElementById('lblFirewallStatus').className = 'badge bg-red';
                                    
                                    if (data.chunk) {
                                        valFirewallText.innerHTML = `<span style="color: #f43f5e; font-weight: bold;">${data.chunk}</span>`;
                                    } else {
                                        valFirewallText.innerHTML = `<span style="color: #f43f5e; font-weight: bold;">[BLOCKED] Threat detected in prompt (${data.category})</span>`;
                                    }
                                    done = true;
                                    break;
                                } else if (data.event === "chunk") {
                                    decisionBadge.innerText = 'PASSED / SAFE';
                                    decisionBadge.className = 'badge bg-green';
                                    outputContainer.style.borderColor = 'rgba(16, 185, 129, 0.4)';
                                    
                                    valFirewallText.innerText += data.chunk;
                                } else if (data.event === "done") {
                                    document.getElementById('lblFirewallStatus').innerText = 'Clean';
                                    document.getElementById('lblFirewallStatus').className = 'badge bg-green';
                                }
                            } catch (e) {
                                // Ignore incomplete chunks
                            }
                        }
                    }
                }
            }
        } catch (err) {
            alert("Streaming connection error: " + err);
        } finally {
            scanBtn.innerText = originalBtnText;
            scanBtn.disabled = false;
        }
        return;
    }

    try {
        const res = await fetch("/api/v1/scan", {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                prompt: promptText,
                enable_scrub: enableScrub,
                enable_redact: enableRedact,
                enable_firewall: enableFirewall,
                enable_shadow: enableShadow,
                downstream_type: downstreamType,
                downstream_model: downstreamModel,
                downstream_token: downstreamToken
            })
        });

        if (res.status === 401) {
            alert("Security error: 401 Unauthorized API Key.");
            return;
        }

        const payload = await res.json();
        outputContainer.style.display = 'block';

        // 1. Set main verdict badge
        const decisionBadge = document.getElementById('lblDecision');
        if (payload.decision === "BLOCK" || !payload.is_safe) {
            decisionBadge.innerText = 'BLOCKED / THREAT';
            decisionBadge.className = 'badge bg-red';
            outputContainer.style.borderColor = 'rgba(244, 63, 94, 0.4)';
        } else {
            decisionBadge.innerText = 'PASSED / SAFE';
            decisionBadge.className = 'badge bg-green';
            outputContainer.style.borderColor = 'rgba(16, 185, 129, 0.4)';
        }

        // 2. Set stats details
        document.getElementById('valCategory').innerText = payload.category;
        
        const evasionBox = document.getElementById('valEvasion');
        if (payload.evasions_detected && payload.evasions_detected.length > 0) {
            evasionBox.innerText = payload.evasions_detected.join(", ");
            evasionBox.style.color = "#f43f5e";
        } else {
            evasionBox.innerText = "None";
            evasionBox.style.color = "#94a3b8";
        }
        
        document.getElementById('valRisk').innerText = (payload.risk_score * 100).toFixed(2) + '%';
        document.getElementById('valLatency').innerText = payload.latency_ms + ' ms';

        // 3. Highlight offensive tokens
        const tokenContainer = document.getElementById('explainability-box');
        const words = promptText.split(/\s+/);
        const explanations = payload.explanations || [];
        
        const highlighted = words.map(word => {
            // Strip punctuation for matching
            const cleanWord = word.toLowerCase().replace(/[^a-z0-9]/g, "");
            const match = explanations.find(e => e.token === cleanWord);
            if (match && match.coefficient > 0.0) {
                return `<span class="token-highlight">${word}</span>`;
            }
            return word;
        }).join(" ");
        tokenContainer.innerHTML = highlighted || "No security features flagged.";

        // 4. Render Active Defense PII card
        if (enableRedact && payload.pii_redacted_text) {
            piiCard.style.display = 'block';
            document.getElementById('valPiiText').innerText = payload.pii_redacted_text;
            document.getElementById('valPiiCount').innerText = payload.pii_items_redacted + " items redacted";
        }

        // 5. Render Active Defense Auto-Scrub card
        if (enableScrub && payload.scrubbed_text) {
            scrubCard.style.display = 'block';
            document.getElementById('valScrubText').innerText = payload.scrubbed_text;
        }

        // 6. Render LLM Output & Output Firewall card
        if ((enableFirewall || downstreamType !== 'mock') && payload.llm_output) {
            firewallCard.style.display = 'block';
            const firewallBadge = document.getElementById('lblFirewallStatus');
            const firewallText = document.getElementById('valFirewallText');
            
            if (payload.firewall_blocked) {
                firewallBadge.innerText = 'Blocked / Outflow Leakage';
                firewallBadge.className = 'badge bg-red';
                firewallText.innerHTML = `<span style="color: #f43f5e; font-weight: 500;">Warning: Response blocked. LLM generated system override key or leaked configuration.</span>`;
            } else {
                firewallBadge.innerText = 'Safe Output';
                firewallBadge.className = 'badge bg-green';
                firewallText.innerText = payload.llm_output;
            }
        }

        // 7. Render A/B Shadow Mode analytics card
        if (enableShadow && payload.shadow_report) {
            shadowCard.style.display = 'block';
            const rScore = (payload.shadow_report.rules_score * 100).toFixed(0);
            const mScore = (payload.shadow_report.ml_score * 100).toFixed(1);
            
            document.getElementById('valShadowRules').innerText = `Rules Verdict: ${payload.shadow_report.rules_verdict} (Score: ${rScore}%)`;
            document.getElementById('valShadowMl').innerText = `ML Model Verdict: ${payload.shadow_report.ml_verdict} (Score: ${mScore}%)`;
            document.getElementById('valShadowLatency').innerText = `ML Inference Overhead: ${payload.shadow_report.ml_latency_ms} ms`;
        }

    } catch (error) {
        alert("API communication error: " + error);
        console.error(error);
    } finally {
        scanBtn.innerText = originalBtnText;
        scanBtn.disabled = false;
    }
}

function toggleDownstreamFields() {
    const type = document.getElementById('selDownstreamType').value;
    const modelDiv = document.getElementById('divModelName');
    const tokenDiv = document.getElementById('divToken');
    const modelInput = document.getElementById('txtDownstreamModel');
    
    if (type === 'mock') {
        modelDiv.style.display = 'none';
        tokenDiv.style.display = 'none';
    } else {
        modelDiv.style.display = 'block';
        tokenDiv.style.display = 'block';
        if (type === 'openai') {
            modelInput.placeholder = 'e.g. gpt-4o-mini';
        } else {
            modelInput.placeholder = 'e.g. meta-llama/Llama-3.2-1B-Instruct';
        }
    }
}
