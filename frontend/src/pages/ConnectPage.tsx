import { ConnectKitButton } from 'connectkit'

export default function ConnectPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-950 px-4 text-white">
      <div className="mx-auto w-full max-w-md text-center">
        <h1 className="mb-2 text-4xl font-bold">kitkat-001</h1>
        <p className="mb-6 text-gray-400">
          TradingView to DEX signal execution
        </p>

        <p className="mb-8 text-sm text-gray-500">
          Automate your trades by connecting TradingView alerts directly to
          decentralized exchanges.
        </p>

        <ConnectKitButton.Custom>
          {({ isConnected, isConnecting, show, truncatedAddress }) => (
            <button
              onClick={show}
              className={
                isConnected
                  ? 'w-full rounded-lg border border-gray-700 bg-gray-800 px-6 py-3 text-lg font-semibold text-white transition-colors hover:bg-gray-700'
                  : 'w-full rounded-lg bg-blue-600 px-6 py-3 text-lg font-semibold text-white transition-colors hover:bg-blue-500 disabled:opacity-50'
              }
              disabled={isConnecting}
            >
              {isConnecting
                ? 'Connecting...'
                : isConnected
                  ? truncatedAddress
                  : 'Connect Wallet'}
            </button>
          )}
        </ConnectKitButton.Custom>

        <div className="mt-8 flex items-center justify-center gap-2 text-sm text-gray-500">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="h-4 w-4 shrink-0 text-gray-400"
          >
            <path
              fillRule="evenodd"
              d="M10 1a4.5 4.5 0 0 0-4.5 4.5V9H5a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2h-.5V5.5A4.5 4.5 0 0 0 10 1Zm3 8V5.5a3 3 0 1 0-6 0V9h6Z"
              clipRule="evenodd"
            />
          </svg>
          <span>
            Signs a message to verify ownership — no fund access granted
          </span>
        </div>
      </div>
    </div>
  )
}
