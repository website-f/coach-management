
import { GoogleGenAI } from "@google/genai";

// Following guidelines: Create a new GoogleGenAI instance right before making an API call.
// The API key is obtained directly and exclusively from process.env.API_KEY.

export const generateTrainingPlan = async (groupLevel: string) => {
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
  try {
    const response = await ai.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: `Generate a 4-week badminton training program for ${groupLevel} group at RSBE Academy. Focus on progression, technical drills, and fitness. Provide output in clear Markdown sections.`
    });
    return response.text;
  } catch (error) {
    console.error("Gemini Error:", error);
    return "Failed to generate training plan. Please try again later.";
  }
};

export const summarizeReflection = async (reflection: string) => {
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
  try {
    const response = await ai.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: `Analyze this badminton coach's reflection and provide 3 actionable improvement tips: "${reflection}"`
    });
    return response.text;
  } catch (error) {
    console.error("Gemini Error:", error);
    return "Reflection summary unavailable.";
  }
};
