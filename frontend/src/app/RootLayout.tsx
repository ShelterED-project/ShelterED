import { Outlet, ScrollRestoration } from 'react-router'
import UpdatePrompt from './UpdatePrompt'

export default function RootLayout() {
  return (
    <>
      <Outlet />
      <ScrollRestoration />
      <UpdatePrompt />
    </>
  )
}
