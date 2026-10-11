import { BrowserRouter, Route, Routes } from "react-router";

function Placeholder({ name }: { name: string }) {
  return (
    <main className="mx-auto max-w-[480px] px-5 py-10">
      <h1 className="display text-4xl">{name}</h1>
    </main>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="*" element={<Placeholder name="Compass" />} />
      </Routes>
    </BrowserRouter>
  );
}
