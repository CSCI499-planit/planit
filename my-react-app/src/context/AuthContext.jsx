import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const token  = sessionStorage.getItem('access_token')
    const userId = sessionStorage.getItem('user_id')
    const name   = sessionStorage.getItem('user_name')
    const email  = sessionStorage.getItem('user_email')
    return token ? { token, userId, name, email } : null
  })

  function login({ access_token, user_id, name, email }) {
    sessionStorage.setItem('access_token', access_token)
    sessionStorage.setItem('user_id',      user_id)
    sessionStorage.setItem('user_name',    name)
    sessionStorage.setItem('user_email',   email)
    setUser({ token: access_token, userId: user_id, name, email })
  }

  function logout() {
    sessionStorage.clear()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
