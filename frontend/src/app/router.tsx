import { createBrowserRouter } from 'react-router'
import AlertWatcher from '@/features/alerts/AlertWatcher'
import RequireRole from '@/features/auth/RequireRole'
import AdminPage from '@/pages/admin/AdminPage'
import LandingPage from '@/pages/landing/LandingPage'
import LoginPage from '@/pages/login/LoginPage'
import NotFoundPage from '@/pages/not-found/NotFoundPage'
import ParentPage from '@/pages/parent/ParentPage'
import RegisterPage from '@/pages/register/RegisterPage'
import ShelterModePage from '@/pages/shelter/ShelterModePage'
import LessonsPage from '@/pages/student/LessonsPage'
import StudentPage from '@/pages/student/StudentPage'
import ClassMapPage from '@/pages/teacher/ClassMapPage'
import RollCallPage from '@/pages/teacher/RollCallPage'
import SchedulePage from '@/pages/teacher/SchedulePage'
import TeacherPage from '@/pages/teacher/TeacherPage'
import RootLayout from './RootLayout'

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: '/', element: <LandingPage /> },
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      {
        element: <RequireRole roles={['student']} />,
        children: [
          {
            // Спостерігач тривог: відкриває режим укриття, коли починається тривога.
            element: <AlertWatcher />,
            children: [
              { path: '/student', element: <StudentPage /> },
              { path: '/student/lessons', element: <LessonsPage /> },
              { path: '/shelter', element: <ShelterModePage /> },
            ],
          },
        ],
      },
      {
        element: <RequireRole roles={['teacher']} />,
        children: [
          { path: '/teacher', element: <TeacherPage /> },
          { path: '/teacher/rollcall', element: <RollCallPage /> },
          { path: '/teacher/schedule', element: <SchedulePage /> },
          { path: '/teacher/map', element: <ClassMapPage /> },
        ],
      },
      {
        element: <RequireRole roles={['parent']} />,
        children: [{ path: '/parent', element: <ParentPage /> }],
      },
      {
        element: <RequireRole roles={['admin']} />,
        children: [{ path: '/admin', element: <AdminPage /> }],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
