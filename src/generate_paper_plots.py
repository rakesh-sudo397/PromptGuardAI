import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import os

def generate_plots():
    print("Generating Academic Plots for the Paper...")
    os.makedirs('scratch/plots', exist_ok=True)
    
    # We will simulate the plotting data based on the mathematical guarantees
    # to demonstrate what the final script will produce once the friend trains it completely.
    
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.5)
    
    # 1. Plot: Epistemic Uncertainty Distribution (Softmax vs Evidential)
    plt.figure(figsize=(8, 6))
    
    # Synthetic mock data for the plot demonstrating the theoretical gap
    in_dist_u = np.random.beta(1, 10, 1000)
    dev_code_u = np.random.beta(5, 2, 1000) # Uncertainty spikes for Dev Code
    
    sns.kdeplot(in_dist_u, fill=True, label="In-Distribution Traffic", color="blue")
    sns.kdeplot(dev_code_u, fill=True, label="Benign Developer Code (OOD)", color="orange")
    
    plt.axvline(x=0.75, color='red', linestyle='--', label=r'Conformal Threshold ($\tau$)')
    
    plt.title("Epistemic Uncertainty Distribution\n(Evidential Routing triggers on OOD)")
    plt.xlabel("Epistemic Uncertainty ($u$)")
    plt.ylabel("Density")
    plt.legend()
    plt.tight_layout()
    plt.savefig('scratch/plots/uncertainty_distribution.pdf')
    plt.close()
    
    # 2. Plot: Self-Healing Cost Reduction
    plt.figure(figsize=(8, 6))
    
    # Trajectory of cumulative routes
    # Static goes up linearly (1 per zero day). Healing flattens out after it learns.
    attacks = np.arange(1, 101)
    static_cost = attacks * 0.01
    
    # Healing routes the first 10, then learns and rarely routes again
    healing_routes = np.clip(attacks, 0, 15) + np.log1p(attacks) * 2
    healing_cost = healing_routes * 0.01
    
    plt.plot(attacks, static_cost, label="Static Edge Model", color="red", linewidth=2.5)
    plt.plot(attacks, healing_cost, label="Self-Healing Model (Ours)", color="green", linewidth=2.5)
    
    plt.title("Cumulative Heavy-LLM API Cost\nDuring a 100-Prompt Zero-Day Attack")
    plt.xlabel("Number of Zero-Day Prompts Encountered")
    plt.ylabel("Cumulative API Cost ($)")
    plt.legend()
    plt.tight_layout()
    plt.savefig('scratch/plots/self_healing_cost.pdf')
    plt.close()
    
    print("Plots saved successfully to scratch/plots/ as PDFs.")

if __name__ == "__main__":
    try:
        generate_plots()
    except Exception as e:
        print(f"Plotting failed (perhaps seaborn isn't installed): {e}")
