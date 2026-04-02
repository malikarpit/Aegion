"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";

type ProfilePreset = {
  key: string;
  name: string;
  icon: string;
  description: string;
  budget: any;
  council: any;
};

export default function ModelSettingsPage() {
  const [presets, setPresets] = useState<ProfilePreset[]>([]);
  const [activePreset, setActivePreset] = useState<string>("balanced");
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    // Phase 85: Fetch the workspace's active settings + the list of presets
    async function loadData() {
      try {
        const [presetsRes, settingsRes] = await Promise.all([
          fetch("/api/v1/model-settings/presets"),
          fetch("/api/v1/model-settings/"),
        ]);
        
        if (presetsRes.ok) {
          setPresets(await presetsRes.json());
        }
        
        if (settingsRes.ok) {
          const settings = await settingsRes.json();
          // Settings engine returns "balanced" default if no record exists
          setActivePreset(settings.active_preset || "balanced");
        }
      } catch (err) {
        console.error("Failed to load model settings:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleApplyPreset = async (presetKey: string) => {
    try {
      const res = await fetch("/api/v1/model-settings/preset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset: presetKey }),
      });
      if (!res.ok) throw new Error("Failed to apply preset");
      
      setActivePreset(presetKey);
      toast({
        title: "Preset Applied",
        description: `Successfully switched to the ${presetKey} model profile.`,
      });
    } catch (err) {
      toast({
        title: "Error",
        description: "Could not apply profile preset.",
        variant: "destructive",
      });
    }
  };

  if (loading) {
    return <div className="p-8 text-center animate-pulse">Loading model settings...</div>;
  }

  return (
    <div className="container mx-auto p-6 max-w-6xl space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Intelligence Routing</h1>
        <p className="text-muted-foreground">
          Configure how the Aegion Kernel routes queries to underlying LLM providers.
          Choose a preset profile to instantly optimize your workspace for cost, speed, or quality.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {presets.map((preset) => (
          <Card 
            key={preset.key} 
            className={`cursor-pointer transition-all hover:border-primary/50 relative overflow-hidden ${
              activePreset === preset.key 
                ? "border-primary shadow-md ring-1 ring-primary" 
                : "border-border/60"
            }`}
            onClick={() => handleApplyPreset(preset.key)}
          >
            {activePreset === preset.key && (
              <div className="absolute top-0 right-0 bg-primary text-primary-foreground text-xs px-2 py-1 rounded-bl-md font-medium">
                Active
              </div>
            )}
            <CardHeader className="pb-3">
              <div className="flex items-center gap-3">
                <span className="text-3xl">{preset.icon}</span>
                <CardTitle className="text-xl">{preset.name}</CardTitle>
              </div>
              <CardDescription className="pt-2">
                {preset.description}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm space-y-2 text-muted-foreground">
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  Max Council Size: {preset.council?.max_size || 1}
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
                  Budget limit: {
                    preset.budget?.daily_limit_usd 
                      ? `$${preset.budget.daily_limit_usd}/day` 
                      : "Unlimited"
                  }
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full ${preset.council?.prefer_cheap ? 'bg-amber-500' : 'bg-purple-500'}" />
                  Prioritize: {preset.council?.prefer_cheap ? 'Cost Efficiency' : 'Top Tier Quality'}
                </li>
              </ul>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>Budget & Cost Tracking</CardTitle>
          <CardDescription>
            View your current token expenditure for this workspace.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Budget analytics are currently aggregated daily. Real-time cost dashboards are available in the VS Code panel.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
