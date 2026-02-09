import { ConnectKitButton } from 'connectkit'

export default function ConnectPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-950 text-white">
      <div className="mx-auto max-w-md text-center">
        <h1 className="mb-2 text-4xl font-bold">kitkat-001</h1>
        <p className="mb-8 text-gray-400">
          TradingView to DEX signal execution
        </p>
        <ConnectKitButton />
        <p className="mt-6 text-sm text-gray-500">
          Signs a message to verify ownership — no fund access granted
        </p>
      </div>
    </div>
  )
}
