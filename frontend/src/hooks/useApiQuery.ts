import { useQuery } from '@tanstack/react-query'
import client from '../api/client'

export function useApiQuery<T>(key: string[], path: string) {
  return useQuery({
    queryKey: key,
    queryFn: () => client.get<T>(path).then((response) => response.data),
  })
}
