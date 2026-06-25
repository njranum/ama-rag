import AskWidget from "@/components/AskWidget";

export default function Home() {
  return (
    <main style={{ maxWidth: 720, margin: "2rem auto", padding: "0 1rem" }}>
      <h1>Ask me anything</h1>
      <p>Ask a question about Nic&apos;s professional background.</p>
      <AskWidget />
    </main>
  );
}
