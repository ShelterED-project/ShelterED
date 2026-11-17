import { Outlet, ScrollRestoration } from 'react-router'
import GlobalLoader from './GlobalLoader'
import UpdatePrompt from './UpdatePrompt'

export default function RootLayout() {
  return (
    <>
      <Outlet />
      <ScrollRestoration />
      <UpdatePrompt />
      <GlobalLoader />
    </>
  )
}
